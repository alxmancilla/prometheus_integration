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
| `Dockerfile` | Builds a custom Prometheus image bundling `prometheus.yml` and `alert.rules.yml`. |
| `prometheus.yml` | Minimal scrape config using Atlas HTTP service discovery (`http_sd_configs`). |
| `alert.rules.yml` | Simple example alerts loaded by the Docker image. |
| `prometheus-atlas.yml` | Advanced config: multiple environments, relabeling, Alertmanager wiring. |
| `atlas_recording_rules.yml` | Pre-aggregated metrics (connections, opcounters, replication lag, latency). |
| `atlas_alerting_rules.yml` | SLO-oriented alerts that reference the recording rules above. |

> **Security:** the YAML files in this repo contain example basic-auth
> credentials and a group ID for demo purposes. Replace them with your own
> values and load secrets from environment variables, a secret manager, or a
> mounted file before using this in any non-throwaway environment.

## Quick start (minimal config)

Build and run the bundled Prometheus image:

```bash
docker build -t my-prometheus .
docker run -p 9090:9090 my-prometheus
```

Then open the Prometheus UI at <http://localhost:9090/> (use your host IP
instead of `localhost` if running Grafana in another container). Prometheus
will use the credentials in `prometheus.yml` to authenticate against the
Atlas discovery endpoint and start scraping each cluster node returned by
service discovery.

On the **Status → Targets** page you should see one target per Atlas node
in the configured project.

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

Run Grafana in Docker:

```bash
docker run -d --name=grafana -p 3000:3000 grafana/grafana-enterprise
```

Open <http://localhost:3000> and log in with the default credentials
(`admin` / `admin`). Then add Prometheus as a data source:

1. **Connections → Data sources → Add data source → Prometheus**
2. **URL:** `http://<host-ip>:9090` (avoid `localhost` if Grafana runs in
   a separate container — it will resolve to the Grafana container itself).
3. Leave **Access** as `Server (default)`.
4. **Save & test**.

Building dashboards is out of scope for this guide; see the
[Grafana docs](https://prometheus.io/docs/visualization/grafana/) for
panel and dashboard guidance.

## References

- [Atlas Prometheus integration](https://www.mongodb.com/docs/atlas/tutorial/monitor-with-prometheus/)
- [Prometheus configuration reference](https://prometheus.io/docs/prometheus/latest/configuration/configuration/)
- [Prometheus recording rules](https://prometheus.io/docs/prometheus/latest/configuration/recording_rules/)
- [Prometheus alerting rules](https://prometheus.io/docs/prometheus/latest/configuration/alerting_rules/)
