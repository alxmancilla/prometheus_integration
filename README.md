# MongoDB Atlas — Prometheus & Grafana Integration

Monitor MongoDB Atlas clusters with Prometheus, Grafana, and Alertmanager.
`docker compose up` gives you:

- **Prometheus** scraping your Atlas clusters through Atlas service discovery.
- **Grafana** with MongoDB's official Atlas dashboards, already connected.
- **Alerts** for the 20 most important Atlas signals (latency, disk, CPU,
  replication, connections, …), each with a runbook.
- **Monitoring-health alerts** that tell you when monitoring itself breaks.
- An optional **org-wide sync script** that covers every project in an Atlas
  organization.

## Contents

- [Before you start](#before-you-start)
- [Quick start](#quick-start)
- [Choose a configuration](#choose-a-configuration)
- [Grafana](#grafana)
- [Alerts](#alerts)
- [Testing](#testing)
- [Repository layout](#repository-layout)
- [More documentation](#more-documentation)

## Before you start

You need:

- An Atlas project with at least one **M10+** cluster. Shared and Flex tiers
  don't support the Prometheus integration.
- The **Prometheus integration** turned on in that project
  ([Atlas docs](https://www.mongodb.com/docs/atlas/tutorial/prometheus-integration/)).
  Note down the **username**, **password**, and **project (group) ID** it gives you.
- **Docker** with Docker Compose.

## Quick start

**1. Add the Atlas password and Grafana login**

```bash
cp secrets/atlas_password.example secrets/atlas_password
$EDITOR secrets/atlas_password      # paste the Atlas Prometheus password
cp .env.example .env
$EDITOR .env                        # pick a Grafana admin password
```

**2. Add your Atlas username and project ID**

In `prometheus.yml`, replace `REPLACE_WITH_ATLAS_USERNAME` and
`REPLACE_WITH_ATLAS_GROUP_ID`.

**3. Start the stack**

```bash
docker compose up -d
```

**4. Check that it works**

| Service | URL | What to check |
|---------|-----|---------------|
| Prometheus | <http://localhost:9090/targets> | One **UP** target per Atlas node |
| Grafana | <http://localhost:3000/> | Log in with the `.env` credentials and open the **MongoDB Atlas** folder |
| Alertmanager | <http://localhost:9093/> | Running |

If a target is down, check the username, password, and project ID. Also check
that the password file is readable by the container user (UID 65534), for
example with `chmod 644 secrets/atlas_password`.

> **Security:** all ports listen on `127.0.0.1` only. Prometheus and
> Alertmanager have no login, so put them behind a reverse proxy before you
> expose them.

## Choose a configuration

| You want to… | Use | How |
|--------------|-----|-----|
| Monitor **one project** | `prometheus.yml` (default) | The Quick start above. |
| Monitor **separate projects for production and staging** | `prometheus-atlas.yml` | Swap the config file in `docker-compose.yml` (see below) and fill in its `REPLACE_WITH_PROD_*` / `REPLACE_WITH_STAGING_*` placeholders. Put the passwords in `secrets/atlas_password_production` and `secrets/atlas_password_staging`. |
| Monitor **every project in an organization** | `prometheus-atlas.yml` + `scripts/atlas_org_sync.py` | See [Org-wide collection](docs/org-wide-collection.md). |
| Ship **a single image** without Compose | `Dockerfile` | `docker build -t my-prometheus .`, then run it with `-v "$(pwd)/secrets:/etc/prometheus/secrets:ro"`. It bundles `prometheus.yml` and the rules. |

To switch to `prometheus-atlas.yml`, edit the `prometheus` service's
`volumes:` in `docker-compose.yml`. Comment out the `prometheus.yml` line,
uncomment the `prometheus-atlas.yml` line, then run `docker compose up -d`.

`prometheus-atlas.yml` also adds `team` and `cluster_tier` labels, so set
those values too. If you only use the org-wide sync, delete its
production and staging jobs. Left with placeholders, they fail and fire
`AtlasScrapeTargetDown`.

Secrets and `.env` are git-ignored; only the `*.example` files are committed.
See [`secrets/README.md`](secrets/README.md).

## Grafana

Grafana connects to Prometheus automatically. Two dashboards appear in the
**MongoDB Atlas** folder:

- **Mongo Metrics:** operations, latency, connections, cache, replication,
  and query targeting.
- **Hardware Metrics:** CPU, memory, disk, and network.

To add a dashboard, drop its JSON file into `grafana/dashboards/`. Changes you
make in the Grafana UI are not saved back to the files, so export and commit
any you want to keep.

When you run Grafana outside Compose, set the data source `url:` in
`grafana/provisioning/datasources/prometheus.yml` to `http://<host-ip>:9090`.

## Alerts

There are three rule files:

| File | What it does |
|------|--------------|
| `atlas_recording_rules.yml` | Precomputes the top-20 signals that alerts and dashboards use. |
| `atlas_alerting_rules.yml` | Atlas alerts with warning and critical levels, for example disk >75% / >90% and read latency >100 ms / >250 ms. |
| `atlas_meta_alerting_rules.yml` | Alerts when monitoring breaks: failed scrapes, missing metrics, or alerts that can't be delivered. |

Every alert links to its section in [`docs/runbooks.md`](docs/runbooks.md).

**Before you rely on the alerts:**

1. **Connect the receivers in `alertmanager.yml`.** The included ones are
   placeholders that **drop every alert**. Critical alerts go to `pager`,
   warnings go to `ticket`, and the always-firing `Watchdog` goes to
   `deadmansswitch`.
2. **Tune the thresholds** to your workload. The included values are starting
   points.

Full list of signals, thresholds, and labels:
[Metrics, recording rules, and alerts](docs/metrics-and-alerts.md).

## Testing

```bash
promtool check rules atlas_*_rules.yml
promtool test rules tests/atlas_rules.test.yml
amtool check-config alertmanager.yml
```

CI (`.github/workflows/validate.yml`) runs these checks plus
`promtool check config` on every push. To confirm the metrics actually arrive
from a real cluster, see [Verifying against a live cluster](docs/verifying.md).

## Repository layout

```
├── docker-compose.yml              Prometheus + Grafana + Alertmanager
├── prometheus.yml                  Basic config (one project)
├── prometheus-atlas.yml            Advanced config (prod/staging, org-wide)
├── atlas_*_rules.yml               Recording, alerting, and monitoring-health rules
├── alertmanager.yml                Alert routing (replace the placeholder receivers)
├── Dockerfile                      Standalone Prometheus image
├── scripts/atlas_org_sync.py       Turns on monitoring for every project in an org
├── scrape_configs/                 Scrape jobs created by the sync script
├── secrets/                        Passwords (only *.example files are committed)
├── grafana/                        Data source and dashboard setup
├── tests/                          Rule unit tests
└── docs/                           Reference docs and runbooks
```

## More documentation

- [Org-wide collection](docs/org-wide-collection.md): monitor every project in an Atlas organization.
- [Metrics, recording rules, and alerts](docs/metrics-and-alerts.md): every signal, alert, threshold, and label.
- [Verifying against a live cluster](docs/verifying.md): PromQL checks that confirm the data is arriving.
- [Runbooks](docs/runbooks.md): what each alert means and what to do about it.
- External: [Atlas Prometheus integration](https://www.mongodb.com/docs/atlas/tutorial/prometheus-integration/) ·
  [Prometheus configuration](https://prometheus.io/docs/prometheus/latest/configuration/configuration/) ·
  [Recording rules](https://prometheus.io/docs/prometheus/latest/configuration/recording_rules/) ·
  [Alerting rules](https://prometheus.io/docs/prometheus/latest/configuration/alerting_rules/)
