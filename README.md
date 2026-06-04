# MongoDB Atlas — Prometheus & Grafana Integration

A reference setup for scraping MongoDB Atlas metrics with Prometheus and
visualizing them with Grafana. The repository contains a minimal "getting
started" configuration as well as a more opinionated production-style
configuration with recording rules and SLO-based alerts.

## Prerequisites

- An Atlas project with an **M10+** cluster (Prometheus integration is not
  available on shared tiers).
- The **Prometheus integration** enabled in Atlas, which produces:
  - a basic-auth **username / password**, and
  - the project's **group ID** (used in the discovery / metrics URL).
  See: [Atlas → Monitor with Prometheus](https://www.mongodb.com/docs/atlas/tutorial/monitor-with-prometheus/).
- Docker (for running Prometheus and Grafana locally).

## Repository layout

| File | Purpose |
|------|---------|
| `docker-compose.yml` | Brings up Prometheus + Grafana (and optionally Alertmanager). Recommended entry point. |
| `Dockerfile` | Builds a self-contained Prometheus image bundling `prometheus.yml` and `alert.rules.yml`. |
| `prometheus.yml` | Minimal scrape config using Atlas HTTP service discovery (`http_sd_configs`). |
| `alert.rules.yml` | Simple example alerts loaded by the Docker image. |
| `prometheus-atlas.yml` | Advanced config: multiple environments, relabeling, Alertmanager wiring. |
| `atlas_recording_rules.yml` | Pre-aggregated metrics (connections, opcounters, replication lag, latency). |
| `atlas_alerting_rules.yml` | SLO-oriented alerts that reference the recording rules above. |
| `alertmanager.yml` | Minimal Alertmanager config (null receiver). Replace before using. |
| `grafana/provisioning/` | Grafana provisioning files; auto-loaded on startup. Registers Prometheus as the default data source. |
| `secrets/` | Runtime secrets mounted into Prometheus. Only `*.example` files are committed. |
| `.env.example` | Template for Grafana admin credentials (copy to `.env`). |

## Configuration

The committed Prometheus configs reference three values that you must set
yourself; none of them are stored in git:

| Placeholder | Where | How to set it |
|-------------|-------|---------------|
| `REPLACE_WITH_ATLAS_USERNAME` | `prometheus.yml`, `prometheus-atlas.yml` | Edit the file inline. |
| `REPLACE_WITH_ATLAS_GROUP_ID` | `prometheus.yml`, `prometheus-atlas.yml` | Edit the file inline. Your Atlas project ID. |
| Atlas password | `secrets/atlas_password` | Copy `secrets/atlas_password.example` to `secrets/atlas_password` and put the real password in it. The file is loaded via Prometheus `password_file:` and bind-mounted read-only into the container. |

The Grafana admin user and password are read from `.env` (see
`.env.example`). Both `.env` and `secrets/atlas_password` are `.gitignore`d.

## Quick start (Docker Compose)

```bash
# 1. Secrets and env
cp secrets/atlas_password.example secrets/atlas_password
$EDITOR secrets/atlas_password                  # paste the Atlas password
cp .env.example .env
$EDITOR .env                                    # set Grafana admin password

# 2. Atlas-specific placeholders
$EDITOR prometheus.yml                          # set username + group ID

# 3. Bring up the stack
docker compose up -d                            # Prometheus + Grafana
# or:
docker compose --profile alerting up -d         # also start Alertmanager
```

Then:

- Prometheus UI: <http://localhost:9090/> → **Status → Targets** should
  show one target per Atlas node returned by service discovery.
- Grafana: <http://localhost:3000/> (credentials from `.env`).
- Alertmanager (if started): <http://localhost:9093/>.

To use the advanced config instead of `prometheus.yml`, edit the
`volumes:` block of the `prometheus` service in `docker-compose.yml` and
swap in `prometheus-atlas.yml`.

## Alternative: self-contained Docker image

`Dockerfile` bakes `prometheus.yml` and `alert.rules.yml` into a single
image. The Atlas password still needs to be mounted at runtime:

```bash
docker build -t my-prometheus .
docker run -p 9090:9090 \
  -v "$(pwd)/secrets:/etc/prometheus/secrets:ro" \
  my-prometheus
```

## Advanced config

`prometheus-atlas.yml` is a richer, production-style template that:

- Defines **separate jobs** for `production` and `staging` environments.
- Uses **`relabel_configs`** to inject `team`, `region`, and
  `cluster_tier` labels at scrape time.
- Uses **`metric_relabel_configs`** to drop high-cardinality / low-value
  series (WiredTiger internals, Go runtime, process metrics) and keep only
  the metrics consumed by the recording and alerting rules.
- Wires Prometheus to an **Alertmanager** at `alertmanager:9093`.
- Loads `atlas_recording_rules.yml` and `atlas_alerting_rules.yml`.

To use it, point Prometheus at this file instead of the default
`prometheus.yml`, update the placeholder group ID, credentials, team, and
region values, and make the rule files available at the paths referenced in
the `rule_files` block.

## Recording and alerting rules

`atlas_recording_rules.yml` pre-aggregates the metrics that dashboards and
alerts query most often, for example:

- `cluster:mongodb_ss_opcounters_total:rate5m` — total ops/sec per cluster
- `cluster:mongodb_ss_connections_utilization:ratio` — current / available connections
- `rs:mongodb_mongod_repl_lag:max` — max replication lag per replica set
- `cluster:mongodb_mongod_op_latencies_reads:avg` and `…_writes:avg` — average read/write latency

`atlas_alerting_rules.yml` builds on those and defines alerts grouped by
SLO signal:

- **Uptime:** `AtlasClusterDown` (`mongodb_up == 0`)
- **Connections:** `AtlasHighConnectionUtilization` (>80%) and `AtlasConnectionUtilizationCritical` (>95%)
- **Replication:** `AtlasReplicationLagHigh` (>10s) and `AtlasReplicationLagCritical` (>60s)
- **Latency:** `AtlasReadLatencyHigh` / `AtlasWriteLatencyHigh` (avg > 100ms)

`alert.rules.yml` is a simpler example set used by the Docker quick-start
image and is independent of the SLO rules above.

## Setting up Grafana

When started via `docker compose`, Grafana is reachable at
<http://localhost:3000/> and the admin user/password are read from `.env`
(`GF_SECURITY_ADMIN_USER` / `GF_SECURITY_ADMIN_PASSWORD`).

The Prometheus data source is **auto-provisioned** from
`grafana/provisioning/datasources/prometheus.yml`, which is bind-mounted
read-only into `/etc/grafana/provisioning/`. On first start Grafana
registers it as the default data source pointing at `http://prometheus:9090`
(the Compose service name). No manual UI steps are required — confirm it
under **Connections → Data sources**.

To run Grafana outside Compose, change the `url:` in the provisioning
file to `http://<host-ip>:9090` (`localhost` resolves to the Grafana
container itself).

Building dashboards is out of scope for this guide; drop dashboard JSON
files under `grafana/provisioning/dashboards/` and add a matching
[dashboard provider](https://grafana.com/docs/grafana/latest/administration/provisioning/#dashboards)
if you want them auto-loaded.

## Alertmanager (optional)

The `alertmanager` service is gated behind the `alerting` Compose profile,
so it only starts when explicitly requested:

```bash
docker compose --profile alerting up -d
```

It loads `alertmanager.yml`, which ships with a single **null receiver**
that silently drops alerts — replace it with a real integration (Slack,
PagerDuty, email, webhook, ...) before relying on it. Note that the
advanced config (`prometheus-atlas.yml`) is already wired to send alerts
to `alertmanager:9093`; the minimal `prometheus.yml` is not.

## References

- [Atlas Prometheus integration](https://www.mongodb.com/docs/atlas/tutorial/monitor-with-prometheus/)
- [Prometheus configuration reference](https://prometheus.io/docs/prometheus/latest/configuration/configuration/)
- [Prometheus recording rules](https://prometheus.io/docs/prometheus/latest/configuration/recording_rules/)
- [Prometheus alerting rules](https://prometheus.io/docs/prometheus/latest/configuration/alerting_rules/)
