# Org-wide collection (all projects)

Back to the [README](../README.md).

Atlas Prometheus integrations are per project, so there is no single
org-wide scrape endpoint. `scripts/atlas_org_sync.py` closes the gap with one
org-level credential:

1. Lists every project in the organization.
2. Ensures each project's Prometheus integration is enabled with HTTP service
   discovery, username `prom_user_<groupId>`, and a shared password.
3. Writes one scrape job per project (`mongodb_atlas_org_<groupId>`, with a
   `project_name` label) to `scrape_configs/atlas_org.yml`. `prometheus-atlas.yml`
   loads that file through `scrape_config_files`.

Requirements: Python 3.8+ (standard library only) and an org-level Atlas
service account (`ATLAS_CLIENT_ID` / `ATLAS_CLIENT_SECRET`) or an API key
(`ATLAS_PUBLIC_KEY` / `ATLAS_PRIVATE_KEY`). The account needs **Organization
Owner** to create integrations; **Organization Read Only** is enough for a
dry run. Add the host running the script to the account's API access list.

The generated jobs are loaded only by `prometheus-atlas.yml`, so switch the
`prometheus` service in `docker-compose.yml` to that file first (the
`scrape_configs/` mount is already in place). The self-contained `Dockerfile`
image doesn't include them.

```bash
cp secrets/atlas_password_org.example secrets/atlas_password_org
$EDITOR secrets/atlas_password_org             # choose the shared password
export ATLAS_ORG_ID=... ATLAS_CLIENT_ID=... ATLAS_CLIENT_SECRET=...

python3 scripts/atlas_org_sync.py                  # dry run: report only
python3 scripts/atlas_org_sync.py --apply \
  --reload-url http://localhost:9090/-/reload      # enable + write + reload
```

Notes:

- Run it on a schedule (cron, CI) to pick up new projects. Use
  `--include` / `--exclude` (regex on the project name) to limit the scope.
- Projects that already have an integration with **different** credentials are
  reported and skipped. `--overwrite` replaces them, which **rotates the
  credentials** and breaks any other consumer that uses them.
- Atlas never returns the integration password, so the script can't confirm it
  matches. After you change `secrets/atlas_password_org`, run with
  `--apply --overwrite` to push the new password to every project.
- Projects without M10+ clusters have no targets, and Atlas may refuse to
  create the integration for them. Those projects show up as errors, and the
  script exits non-zero.
- The jobs match the `mongodb_atlas_.*` regex in `atlas_meta_alerting_rules.yml`,
  so scrape failures are alerted on.

