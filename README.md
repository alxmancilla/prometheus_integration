# MongoDB Atlas — Prometheus & Grafana Integration

A reference setup for scraping MongoDB Atlas metrics with Prometheus and
visualizing them with Grafana. The repository contains a minimal "getting
started" configuration as well as a more opinionated production-style
configuration with top-20 recording rules and recommended Atlas alerts.

## Prerequisites

- An Atlas project with an **M10+** cluster (Prometheus integration is not
  available on shared tiers).
- The **Prometheus integration** enabled in Atlas, which produces:
  - a basic-auth **username / password**, and
  - the project's **group ID** (used in the discovery / metrics URL).
  See: [Atlas → Monitor with Prometheus](https://www.mongodb.com/docs/atlas/tutorial/prometheus-integration/).
- Docker (for running Prometheus and Grafana locally).

## Repository layout

| File | Purpose |
|------|---------|
| `docker-compose.yml` | Brings up Prometheus + Grafana (and optionally Alertmanager). Recommended entry point. |
| `Dockerfile` | Builds a self-contained Prometheus image bundling `prometheus.yml` and the Atlas rule files. |
| `prometheus.yml` | Minimal scrape config using Atlas HTTP service discovery (`http_sd_configs`). Loads the top-20 recording and alerting rules. |
| `prometheus-atlas.yml` | Advanced config: production/staging jobs, relabeling, Alertmanager wiring. |
| `atlas_recording_rules.yml` | Pre-aggregated top-20 metrics for latency, CPU, disk, connections, cache, query behavior, replication, memory, network, and process health. |
| `atlas_alerting_rules.yml` | Recommended Atlas alerts that reference the recording rules above. |
| `alertmanager.yml` | Minimal Alertmanager config (null receiver). Replace before using. |
| `grafana/provisioning/` | Grafana provisioning files; auto-loaded on startup. Registers Prometheus as the default data source. |
| `secrets/` | Runtime secrets mounted into Prometheus. Only `*.example` files are committed. |
| `.env.example` | Template for Grafana admin credentials (copy to `.env`). |

## Configuration

The committed Prometheus configs reference values that you must set yourself;
none of them are stored in git:

| Placeholder | Where | How to set it |
|-------------|-------|---------------|
| `REPLACE_WITH_ATLAS_USERNAME` | `prometheus.yml`, `prometheus-atlas.yml` | Edit the file inline. |
| `REPLACE_WITH_ATLAS_GROUP_ID` | `prometheus.yml` | Edit the file inline. Your Atlas project ID. |
| `REPLACE_WITH_PROD_ATLAS_GROUP_ID` / `REPLACE_WITH_STAGING_ATLAS_GROUP_ID` | `prometheus-atlas.yml` | Edit the file inline. Use distinct Atlas project IDs when you enable both advanced jobs. |
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

`Dockerfile` bakes `prometheus.yml`, `atlas_recording_rules.yml`, and
`atlas_alerting_rules.yml` into a single image. The Atlas password still
needs to be mounted at runtime:

```bash
docker build -t my-prometheus .
docker run -p 9090:9090 \
  -v "$(pwd)/secrets:/etc/prometheus/secrets:ro" \
  my-prometheus
```

## Advanced config

`prometheus-atlas.yml` is a richer, production-style template that:

- Defines **separate jobs** for `production` and `staging` environments.
- Uses Atlas **HTTP service discovery** for each environment.
- Uses **`relabel_configs`** to inject `team`, `region`, and
  `cluster_tier` labels at scrape time and to derive a `hostname` label from
  the discovered target address.
- Uses **`metric_relabel_configs`** to drop Go/client runtime noise and keep
  Atlas/MongoDB metric series consumed by the recording and alerting rules.
- Wires Prometheus to an **Alertmanager** at `alertmanager:9093`.
- Loads `atlas_recording_rules.yml` and `atlas_alerting_rules.yml`.

To use it, point Prometheus at this file instead of the default
`prometheus.yml`, update the placeholder group IDs, credentials, team, and
region values, and make the rule files available at the paths referenced in
the `rule_files` block.

## Signals, recording rules, and alerts

The scrape configs retain Atlas/MongoDB metric series and the rule files
cover the following top-20 signals:

| # | Signal | Source metrics |
|---|--------|----------------|
| 1 | Latency | `mongodb_opLatencies_reads_*`, `mongodb_opLatencies_writes_*`, `mongodb_opLatencies_commands_*` |
| 2 | CPU | `mongodb_system_cpu_normalized_*` |
| 3 | Disk I/O | `mongodb_disk_partition_iops_*`, `mongodb_disk_partition_latency_*` |
| 4 | Disk Space | `mongodb_disk_partition_space_used`, `mongodb_disk_partition_space_free` |
| 5 | Connections | `mongodb_connections_current`, `mongodb_connections_available` |
| 6 | WiredTiger Cache | `mongodb_wiredTiger_cache_*` |
| 7 | Query Targeting | `mongodb_metrics_queryExecutor_scannedObjects`, `mongodb_metrics_document_returned` |
| 8 | Global Lock Queue | `mongodb_globalLock_currentQueue_*` |
| 9 | Opcounters | `mongodb_opcounters_*` |
| 10 | Scan and Order | `mongodb_metrics_operation_scanAndOrder`, `mongodb_metrics_query_sort_spillToDisk` |
| 11 | Replication Safety | computed replication headroom from oplog window and secondary lag |
| 12 | Oplog Capacity | `mongodb_oplog_latestOptime`, `mongodb_oplog_earliestOptime` |
| 13 | Oplog Churn | `mongodb_oplog_rate_gb_per_hour` / `mongodb_oplog_rateGbPerHour` when exposed |
| 14 | Host Memory | `mongodb_system_memory_available`, `mongodb_system_memory_used` |
| 15 | Page Faults | `mongodb_extra_info_page_faults` |
| 16 | Query Executor | `mongodb_metrics_queryExecutor_scanned`, `mongodb_metrics_queryExecutor_scannedObjects` |
| 17 | Network | `mongodb_network_bytesIn`, `mongodb_network_bytesOut`, `mongodb_network_numRequests` |
| 18 | Process Memory | `mongodb_mem_resident`, `mongodb_mem_virtual` |
| 19 | Cache Ratios | computed WT cache fill and dirty fill ratios |
| 20 | Process CPU | `mongodb_process_cpu_normalized_*` when exposed |

The query-performance context rules also accept optional custom gauges from
an Atlas Admin API collector:

- `mongodb_namespace_slow_queries_total` / `atlas_namespace_slow_queries_total`
- `mongodb_namespace_p95_execution_time_ms` / `atlas_namespace_p95_execution_time_ms`
- `mongodb_query_targeting_scanned_objects_per_returned` / `QUERY_TARGETING_SCANNED_OBJECTS_PER_RETURNED`

Performance Advisor fix-layer gauges are also supported when exported by a
custom collector:

- `atlas_performance_advisor_index_recommendations`
- `atlas_performance_advisor_unused_indexes`
- `atlas_performance_advisor_redundant_indexes`

Custom namespace and Performance Advisor gauges should include `cl_id`,
`namespace`, `database`, and `collection` labels. The recording rules also
preserve `job`, `environment`, `region`, and `availability_zone` when those
labels are present.

> **Metric availability note:** Atlas Prometheus metric availability can vary
> by Atlas version, project settings, and whether host-measurement series are
> exposed in the Prometheus surface. Rules for CPU, disk, host memory, oplog
> churn, and process CPU produce empty series when the underlying metrics are
> not present. Namespace and Performance Advisor rules also produce empty
> series unless a custom Atlas Admin API collector exports those gauges. Verify
> all alert inputs against a live target before enabling notifications.

### Recording rules (`atlas_recording_rules.yml`)

Pre-aggregated series that dashboards and alerts query directly. Common
examples:

- `node:mongodb_oplatencies_reads:avg_usec` / `node:mongodb_oplatencies_writes:avg_usec` — average read/write latency
- `node:mongodb_query_targeting:ratio` — scanned objects per returned document
- `node:mongodb_disk_space_used:ratio` — disk usage ratio
- `node:mongodb_connections_utilization:ratio` — current / tier-limit connections, where Atlas exposes available connections
- `node:mongodb_oplog_window:seconds` — oplog window per node
- `node:mongodb_replication_headroom:seconds` — oplog window minus secondary lag
- `node:mongodb_wiredtiger_cache_fill:ratio` / `node:mongodb_wiredtiger_cache_dirty_fill:ratio` — WT cache ratios
- `cluster:mongodb_opcounters_total:rate5m` — total operation rate per cluster
- `namespace:mongodb_slow_queries:rate5m` — slow query rate by namespace when custom-exported
- `namespace:mongodb_p95_execution_time:ms` — P95 execution time by namespace when custom-exported
- `namespace:atlas_performance_advisor_index_recommendations:count` — index recommendations by namespace when custom-exported

### Alerting rules (`atlas_alerting_rules.yml`)

Grouped by signal, with warning + critical tiers where useful. Recommended
alerts are implemented with the requested starting thresholds:

| Group | Alerts |
|-------|--------|
| Query targeting | `AtlasQueryTargetingRatioHigh` (>100, 5m), `AtlasQueryTargetingRatioCritical` (>1000, 5m) |
| Read/write latency | `AtlasReadLatencyHigh` / `AtlasWriteLatencyHigh` (>100ms, 5m), critical variants (>250ms, 5m) |
| Disk usage | `AtlasDiskUsageHigh` (>75%, 5m), `AtlasDiskUsageCritical` (>90%, 5m) |
| Oplog window | `AtlasOplogWindowLow` (<24h, 5m), `AtlasOplogWindowCritical` (<1h, 10m) |
| Connections | `AtlasConnectionUtilizationHigh` (>80%, 5m), `AtlasConnectionUtilizationCritical` (>90%, 5m) |
| Replication headroom | `AtlasReplicationHeadroomLow` (<12h, 5m), `AtlasReplicationHeadroomCritical` (<1h, 5m) |
| System memory available | `AtlasSystemMemoryAvailableLow` (<75% of 7-day baseline, 10m), `AtlasSystemMemoryAvailableCritical` (<5%, 10m) |
| Page faults | `AtlasPageFaultsHigh` (>50/s, 5m), `AtlasPageFaultsCritical` (>100/s, 5m) |
| Queued readers/writers | `AtlasQueuedReadersOrWriters` (sustained queue growth, 5m), `AtlasQueuedReadersOrWritersCritical` (>10 queued readers or writers, 5m) |
| Primary election | `AtlasPrimaryElectionDetected` (any role change), `AtlasFrequentPrimaryElections` (>1 role change in 1h) |
| CPU saturation | `AtlasCpuSaturationHigh` (>80%, 5m), `AtlasCpuSaturationCritical` (>90%, 5m) |

> **Thresholds are starting points.** The values above are drawn from
> MongoDB Atlas best-practice guidance and are meant to be calibrated to
> your workload, SLAs, and node roles before you enable notifications.
> Some alerts are only meaningful on specific node types (e.g. dirty
> cache on `PRIMARY`); the header of `atlas_alerting_rules.yml` shows
> how to scope them with a `node_type` / `role` label matcher.

Analytics nodes usually need more relaxed latency, CPU, and query-targeting
thresholds because they are outside the primary application read/write path.
The shipped alerts keep strict thresholds on `ELECTABLE` nodes; duplicate the
same rules with `node_type="ANALYTICS"` and looser thresholds if analytics
node alerting is required.

Every node-level alert includes a `context` annotation with `hostname`,
`instance`, `node_type`, `role`, `availability_zone`, and `region`. The
advanced config injects `region` and derives `hostname` from the scrape target.
The minimal config also derives `hostname`; `availability_zone` and `region`
are preserved when Atlas service discovery or relabeling provides them.

### Query Performance Signals

Prometheus covers the cluster and node signals directly. Collection/query
context is represented by optional namespace-level series:

- Slow query rate by namespace: `namespace:mongodb_slow_queries:rate5m`
- Documents examined versus returned: `namespace:mongodb_query_targeting:ratio`
- P95 execution time per collection: `namespace:mongodb_p95_execution_time:ms`
- In-memory sort rate: `node:mongodb_scan_and_order:rate5m`

The namespace-level slow-query and P95 series require an Atlas Admin API
collector because Atlas exposes that detail through Namespace Insights,
Query Profiler, and measurements APIs rather than the basic Prometheus scrape
in every project.

Expected custom gauge shape examples:

```promql
mongodb_namespace_slow_queries_total{cl_id="...", namespace="db.collection", database="db", collection="collection"}
mongodb_namespace_p95_execution_time_ms{cl_id="...", namespace="db.collection", database="db", collection="collection"}
```

### Performance Advisor

Performance Advisor is modeled as the fix layer that pairs with Prometheus
alerts. If an Atlas Admin API collector exports the supported custom gauges,
Prometheus records:

- `namespace:atlas_performance_advisor_index_recommendations:count`
- `namespace:atlas_performance_advisor_unused_indexes:count`
- `namespace:atlas_performance_advisor_redundant_indexes:count`

Expected custom gauge shape examples:

```promql
atlas_performance_advisor_index_recommendations{cl_id="...", namespace="db.collection", database="db", collection="collection"}
atlas_performance_advisor_unused_indexes{cl_id="...", namespace="db.collection", database="db", collection="collection"}
atlas_performance_advisor_redundant_indexes{cl_id="...", namespace="db.collection", database="db", collection="collection"}
```

Recommended triage flow:

1. Prometheus fires a latency or query-targeting alert.
2. Atlas Namespace Insights identifies the hot collection.
3. Atlas Query Profiler identifies the slow query shape.
4. Performance Advisor surfaces the index fix.
5. Prometheus confirms that metrics return to baseline.

## Verifying against a live cluster

Once Prometheus is scraping a real Atlas project, use these checks to
confirm the metrics assumed by the recording and alerting rules actually
land. Run each query from the Prometheus UI (<http://localhost:9090/graph>)
or via the HTTP API.

1. **Target is up and authenticated**

   ```promql
   up{job=~"AlejandroMR-mongo-metrics|mongodb_atlas_.*"}
   ```

   Expect `1` per replica-set member. `0` means the scrape is failing —
   check credentials, group ID, and the Prometheus target-error message.

2. **Core signals are present** — each of these should return at least
   one series:

   ```promql
   mongodb_up
   mongodb_opcounters_query
   mongodb_connections_current
   mongodb_wiredTiger_cache_bytes_currently_in_the_cache
   mongodb_wiredTiger_cache_tracked_dirty_bytes_in_the_cache
   mongodb_metrics_queryExecutor_scannedObjects
   mongodb_metrics_document_returned
   mongodb_oplog_latestOptime
   mongodb_oplog_earliestOptime
   ```

3. **Optional host metrics are present** — these rules are expected to be
   empty if Atlas does not expose host measurements through Prometheus:

   ```promql
   mongodb_system_cpu_normalized_user
   mongodb_disk_partition_space_used
   mongodb_system_memory_available
   mongodb_process_cpu_normalized_user
   ```

4. **Recording rules are producing series**

   ```promql
   node:mongodb_oplatencies_reads:avg_usec
   node:mongodb_query_targeting:ratio
   node:mongodb_connections_utilization:ratio
   node:mongodb_oplog_window:seconds
   node:mongodb_wiredtiger_cache_dirty_fill:ratio
   ```

   An empty result usually means the underlying raw metric is missing or
   labeled differently on your cluster — start with step 2 or 3.

5. **Node context labels are present** — alert annotations use these labels
   when available:

   ```promql
   count by (hostname, instance, node_type, role, availability_zone, region) (mongodb_up)
   ```

   `hostname` is derived by the scrape config. `region` is injected by
   `prometheus-atlas.yml`; in the minimal config it appears only if Atlas
   service discovery provides it. `availability_zone` appears only when Atlas
   service discovery provides it.

6. **Optional namespace and Performance Advisor series are present** — these
   return data only when a custom Atlas Admin API collector exports them:

   ```promql
   namespace:mongodb_slow_queries:rate5m
   namespace:mongodb_query_targeting:ratio
   namespace:mongodb_p95_execution_time:ms
   namespace:atlas_performance_advisor_index_recommendations:count
   namespace:atlas_performance_advisor_unused_indexes:count
   namespace:atlas_performance_advisor_redundant_indexes:count
   ```

7. **Rule health** — <http://localhost:9090/rules> lists every group and
   flags evaluation errors (bad label matchers, division-by-zero
   protection, etc.) that don't show up in `promtool check rules`.

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

- [Atlas Prometheus integration](https://www.mongodb.com/docs/atlas/tutorial/prometheus-integration/)
- [Prometheus configuration reference](https://prometheus.io/docs/prometheus/latest/configuration/configuration/)
- [Prometheus recording rules](https://prometheus.io/docs/prometheus/latest/configuration/recording_rules/)
- [Prometheus alerting rules](https://prometheus.io/docs/prometheus/latest/configuration/alerting_rules/)
