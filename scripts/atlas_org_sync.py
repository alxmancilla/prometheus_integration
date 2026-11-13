#!/usr/bin/env python3
"""Enable the Atlas Prometheus integration across every project in an org and
generate Prometheus scrape configs for them.

For each project in the organization the script:
  1. Reads the project's PROMETHEUS third-party integration.
  2. With --apply, creates it (or, with --overwrite, replaces it) using the
     shared password and a per-project username (default prom_user_<groupId>).
  3. Emits one scrape job per project whose integration uses our credentials
     into a file loaded by Prometheus via `scrape_config_files`.

Dry-run by default: nothing in Atlas changes without --apply.

Authentication (org-level, Organization Owner is required for --apply;
Organization Read Only is enough for a dry run):
  ATLAS_CLIENT_ID / ATLAS_CLIENT_SECRET   service account (preferred), or
  ATLAS_PUBLIC_KEY / ATLAS_PRIVATE_KEY    programmatic API key (digest auth)
  ATLAS_ORG_ID                            organization ID (or --org-id)

Standard library only.
"""

import argparse
import base64
import json
import os
import re
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

BASE_URL = "https://cloud.mongodb.com"
API = BASE_URL + "/api/atlas/v2"
ACCEPT = "application/vnd.atlas.2023-01-01+json"
JOB_PREFIX = "mongodb_atlas_org_"  # must match the job regex in atlas_meta_alerting_rules.yml


class AtlasClient:
    def __init__(self):
        self.token = None
        self.token_expiry = 0
        self.opener = urllib.request.build_opener()
        cid, csecret = os.environ.get("ATLAS_CLIENT_ID"), os.environ.get("ATLAS_CLIENT_SECRET")
        pub, priv = os.environ.get("ATLAS_PUBLIC_KEY"), os.environ.get("ATLAS_PRIVATE_KEY")
        if cid and csecret:
            self.client_creds = (cid, csecret)
        elif pub and priv:
            self.client_creds = None
            mgr = urllib.request.HTTPPasswordMgrWithDefaultRealm()
            mgr.add_password(None, BASE_URL, pub, priv)
            self.opener = urllib.request.build_opener(urllib.request.HTTPDigestAuthHandler(mgr))
        else:
            sys.exit("Set ATLAS_CLIENT_ID/ATLAS_CLIENT_SECRET or ATLAS_PUBLIC_KEY/ATLAS_PRIVATE_KEY")

    def _bearer(self):
        if time.time() < self.token_expiry - 60:
            return self.token
        cid, csecret = self.client_creds
        req = urllib.request.Request(
            BASE_URL + "/api/oauth/token",
            data=b"grant_type=client_credentials",
            headers={
                "Authorization": "Basic " + base64.b64encode(f"{cid}:{csecret}".encode()).decode(),
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.load(resp)
        self.token = body["access_token"]
        self.token_expiry = time.time() + int(body.get("expires_in", 3600))
        return self.token

    def request(self, method, path, body=None):
        """Returns (status, parsed_json). 404 is returned, other errors raise."""
        data = json.dumps(body).encode() if body is not None else None
        for attempt in range(5):
            headers = {"Accept": ACCEPT}
            if data is not None:
                headers["Content-Type"] = ACCEPT
            if self.client_creds:
                headers["Authorization"] = "Bearer " + self._bearer()
            req = urllib.request.Request(API + path, data=data, method=method, headers=headers)
            try:
                with self.opener.open(req, timeout=60) as resp:
                    raw = resp.read()
                    return resp.status, (json.loads(raw) if raw else None)
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    return 404, None
                if e.code in (429, 500, 502, 503, 504) and attempt < 4:
                    time.sleep(int(e.headers.get("Retry-After") or 2 ** (attempt + 1)))
                    continue
                detail = e.read().decode(errors="replace")
                raise RuntimeError(f"{method} {path} -> HTTP {e.code}: {detail}") from None
        raise RuntimeError(f"{method} {path}: retries exhausted")

    def paginate(self, path):
        page = 1
        while True:
            sep = "&" if "?" in path else "?"
            _, body = self.request("GET", f"{path}{sep}itemsPerPage=500&pageNum={page}")
            results = body.get("results", [])
            yield from results
            if not results or page * 500 >= body.get("totalCount", 0):
                return
            page += 1


def sync_project(client, project, username, password, apply, overwrite):
    """Returns (status, scrapeable) for one project."""
    gid = project["id"]
    path = f"/groups/{gid}/integrations/PROMETHEUS"
    status, current = client.request("GET", path)
    desired = {
        "type": "PROMETHEUS",
        "enabled": True,
        "serviceDiscovery": "http",
        "username": username,
        "password": password,
    }

    if status == 404:
        if not apply:
            return "missing (would create)", False
        client.request("POST", path, desired)
        return "created", True

    matches = (
        current.get("enabled")
        and current.get("username") == username
        and current.get("serviceDiscovery") == "http"
    )
    if matches:
        # Atlas never returns the password, so we cannot verify it. With
        # --overwrite we re-push it to guarantee it matches the password file.
        if apply and overwrite:
            client.request("PUT", path, desired)
            return "ok (password re-applied)", True
        return "ok", True

    if not overwrite:
        return f"foreign config (username={current.get('username')!r}); use --overwrite", False
    if not apply:
        return "foreign config (would overwrite)", False
    client.request("PUT", path, desired)
    return "overwritten", True


def q(value):
    """Quote a scalar for YAML (JSON strings are valid YAML)."""
    return json.dumps(value)


def render_scrape_configs(projects, username_tmpl, password_file, refresh):
    lines = [
        "# GENERATED by scripts/atlas_org_sync.py -- do not edit by hand.",
        "scrape_configs:",
    ]
    for p in projects:
        gid, user = p["id"], username_tmpl.format(group_id=p["id"])
        auth = [
            "      basic_auth:",
            f"        username: {q(user)}",
            f"        password_file: {q(password_file)}",
        ]
        lines += [
            f"  - job_name: {q(JOB_PREFIX + gid)}",
            "    scrape_interval: 60s",
            "    scrape_timeout: 30s",
            "    scheme: https",
            "    metrics_path: /metrics",
            "    basic_auth:",
            f"      username: {q(user)}",
            f"      password_file: {q(password_file)}",
            "    http_sd_configs:",
            f"      - url: {q(f'{BASE_URL}/prometheus/v1.0/groups/{gid}/discovery')}",
            f"        refresh_interval: {refresh}",
            *["  " + a for a in auth],
            "    relabel_configs:",
            "      - source_labels: [__address__]",
            "        target_label: hostname",
            "      - target_label: project_name",
            f"        replacement: {q(p['name'])}",
            "    metric_relabel_configs:",
            "      - source_labels: [__name__]",
            '        regex: "go_.*|promhttp_.*|process_.*"',
            "        action: drop",
            "      - source_labels: [__name__]",
            '        regex: "mongodb_.*|atlas_.*|hardware_.*|QUERY_TARGETING_.*"',
            "        action: keep",
        ]
    if not projects:
        lines[-1] = "scrape_configs: []"
    return "\n".join(lines) + "\n"


def write_atomic(path, content):
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=".tmp-", suffix=".yml")
    with os.fdopen(fd, "w") as f:
        f.write(content)
    os.chmod(tmp, 0o644)
    os.replace(tmp, path)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--org-id", default=os.environ.get("ATLAS_ORG_ID"))
    ap.add_argument("--password-file", default="secrets/atlas_password_org",
                    help="local file with the shared Prometheus password (default: %(default)s)")
    ap.add_argument("--container-password-file", default="/etc/prometheus/secrets/atlas_password_org",
                    help="path of the same file inside the Prometheus container (default: %(default)s)")
    ap.add_argument("--username-template", default="prom_user_{group_id}",
                    help="per-project Prometheus username (default: %(default)s)")
    ap.add_argument("--output", default="scrape_configs/atlas_org.yml",
                    help="generated scrape config file (default: %(default)s)")
    ap.add_argument("--include", help="regex; only projects whose name matches")
    ap.add_argument("--exclude", help="regex; skip projects whose name matches")
    ap.add_argument("--refresh-interval", default="2m")
    ap.add_argument("--apply", action="store_true", help="create/update integrations in Atlas")
    ap.add_argument("--overwrite", action="store_true",
                    help="replace integrations configured with other credentials (rotates them!)")
    ap.add_argument("--reload-url", help="e.g. http://localhost:9090/-/reload, POSTed after writing")
    args = ap.parse_args()

    if not args.org_id:
        sys.exit("Set ATLAS_ORG_ID or pass --org-id")
    with open(args.password_file) as f:
        password = f.read().rstrip("\n")
    if not password:
        sys.exit(f"{args.password_file} is empty")

    client = AtlasClient()
    projects = list(client.paginate(f"/orgs/{args.org_id}/groups"))
    if args.include:
        projects = [p for p in projects if re.search(args.include, p["name"])]
    if args.exclude:
        projects = [p for p in projects if not re.search(args.exclude, p["name"])]

    scrapeable, failures = [], 0
    for p in sorted(projects, key=lambda p: p["name"]):
        username = args.username_template.format(group_id=p["id"])
        try:
            status, ok = sync_project(client, p, username, password, args.apply, args.overwrite)
        except RuntimeError as e:
            status, ok, failures = f"ERROR: {e}", False, failures + 1
        print(f"{p['name']:<40} {p['id']}  {status}")
        if ok:
            scrapeable.append(p)

    write_atomic(args.output, render_scrape_configs(
        scrapeable, args.username_template, args.container_password_file, args.refresh_interval))
    print(f"\n{len(scrapeable)}/{len(projects)} projects written to {args.output}"
          + ("" if args.apply else " (dry run: Atlas unchanged)"))

    if args.reload_url:
        try:
            urllib.request.urlopen(urllib.request.Request(args.reload_url, method="POST"), timeout=10)
            print(f"Reloaded Prometheus via {args.reload_url}")
        except (urllib.error.URLError, OSError) as e:
            print(f"WARNING: reload failed: {e}", file=sys.stderr)
            failures += 1

    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
