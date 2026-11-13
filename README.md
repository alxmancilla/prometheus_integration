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
| `docker-compose.yml` | Brings up Prometheus + Grafana + Alertmanager (pinned versions, localhost-only ports). Recommended entry point. |
| `Dockerfile` | Builds a self-contained Prometheus image bundling `prometheus.yml` and the Atlas rule files. |
| `prometheus.yml` | Minimal scrape config using Atlas HTTP service discovery (`http_sd_configs`). Loads the top-20 recording and alerting rules. |
| `prometheus-atlas.yml` | Advanced config: production/staging jobs, relabeling, Alertmanager wiring. |
| `atlas_recording_rules.yml` | Pre-aggregated top-20 metrics for latency, CPU, disk, connections, cache, query behavior, replication, memory, network, and process health. |
| `atlas_alerting_rules.yml` | Recommended Atlas alerts that reference the recording rules above. |
| `atlas_meta_alerting_rules.yml` | Monitoring-health alerts: scrape/SD failures, missing rule inputs, rule and notification failures, Watchdog heartbeat. |
| `alertmanager.yml` | Severity routing + inhibition rules. Receivers are placeholders; wire them before using. |
| `tests/` | `promtool test rules` unit tests for the rule files. |
| `.github/workflows/validate.yml` | CI: `promtool check config/rules`, rule unit tests, `amtool check-config`. |
| `grafana/provisioning/` | Grafana provisioning files; auto-loaded on startup. Registers Prometheus as the default data source. |
| `secrets/` | Runtime secrets mounted into Prometheus. Only `*.example` files are committed. |
| `.env.example` | Template for Grafana admin credentials (copy to `.env`). |

## Configuration

The committed Prometheus configs reference values that you must set yourself;
none of them are stored in git:

| Placeholder | Where | How to set it |
|-------------|-------|---------------|
| `REPLACE_WITH_ATLAS_USERNAME` | `prometheus.yml` | Edit the file inline. |
| `REPLACE_WITH_PROD_ATLAS_USERNAME` / `REPLACE_WITH_STAGING_ATLAS_USERNAME` | `prometheus-atlas.yml` | Edit the file inline. Atlas Prometheus credentials are per project. |
| `REPLACE_WITH_ATLAS_GROUP_ID` | `prometheus.yml` | Edit the file inline. Your Atlas project ID. |
| `REPLACE_WITH_PROD_ATLAS_GROUP_ID` / `REPLACE_WITH_STAGING_ATLAS_GROUP_ID` | `prometheus-atlas.yml` | Edit the file inline. Use distinct Atlas project IDs when you enable both advanced jobs. |
| Atlas password | `secrets/atlas_password` | Copy `secrets/atlas_password.example` to `secrets/atlas_password` and put the real password in it. The file is loaded via Prometheus `password_file:` and bind-mounted read-only into the container. |
| Atlas passwords (advanced config) | `secrets/atlas_password_production`, `secrets/atlas_password_staging` | Same as above, one file per Atlas project. |

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

# 3. Alert receivers
$EDITOR alertmanager.yml                        # wire pager / ticket / deadmansswitch

# 4. Bring up the stack
docker compose up -d
```

The Prometheus container runs as `nobody` (UID 65534), so
`secrets/atlas_password` must be readable by that user (e.g. `chmod 644`, or
`chown 65534` + `chmod 400`). An unreadable secret shows up as a failing scrape
and fires `AtlasScrapeTargetDown`.

All ports are bound to `127.0.0.1`. Prometheus and Alertmanager have no
authentication; put them behind a reverse proxy before exposing them.

Then:

- Prometheus UI: <http://localhost:9090/> → **Status → Targets** should
  show one target per Atlas node returned by service discovery.
- Grafana: <http://localhost:3000/> (credentials from `.env`).
- Alertmanager: <http://localhost:9093/>.

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
- Uses **`relabel_configs`** to inject `team`, `environment`, and
  `cluster_tier` labels at scrape time (Atlas already provides `region`,
  `provider`, `cl_name`, etc., so those are not overridden) and to derive a `hostname` label from
  the discovered target address.
- Uses **`metric_relabel_configs`** to drop Go/client runtime noise and keep
  Atlas/MongoDB metric series consumed by the recording and alerting rules.
- Wires Prometheus to an **Alertmanager** at `alertmanager:9093`.
- Loads `atlas_recording_rules.yml` and `atlas_alerting_rules.yml`.

To use it, point Prometheus at this file instead of the default
`prometheus.yml`, update the placeholder group IDs, credentials, and team
values, and make the rule files available at the paths referenced in
the `rule_files` block.

## Signals, recording rules, and alerts

The scrape configs retain Atlas/MongoDB metric series and the rule files
cover the following top-20 signals:

| # | Signal | Source metrics |
|---|--------|----------------|
| 1 | Latency | `mongodb_opLatencies_reads_*`, `mongodb_opLatencies_writes_*`, `mongodb_opLatencies_commands_*` |
| 2 | CPU | `hardware_system_cpu_*_milliseconds` ÷ `hardware_platform_num_logical_cpus` |
| 3 | Disk I/O | `hardware_disk_metrics_{read,write}_count`, `hardware_disk_metrics_{read,write}_time_milliseconds` |
| 4 | Disk Space | `hardware_disk_metrics_disk_space_used_bytes`, `hardware_disk_metrics_disk_space_free_bytes` |
| 5 | Connections | `mongodb_connections_current`, `mongodb_connections_available` |
| 6 | WiredTiger Cache | `mongodb_wiredTiger_cache_*` |
| 7 | Query Targeting | `mongodb_metrics_queryExecutor_scannedObjects`, `mongodb_metrics_document_returned` |
| 8 | Global Lock Queue | `mongodb_globalLock_currentQueue_*` |
| 9 | Opcounters | `mongodb_opcounters_*` |
| 10 | Scan and Order | `mongodb_metrics_operation_scanAndOrder`, `mongodb_metrics_query_sort_spillToDisk` |
| 11 | Replication Safety | computed replication headroom from oplog window and secondary lag |
| 12 | Oplog Capacity | `mongodb_oplog_latestOptime`, `mongodb_oplog_earliestOptime` |
| 13 | Oplog Churn | `mongodb_oplog_rate_gb_per_hour` / `mongodb_oplog_rateGbPerHour` when exposed |
| 14 | Host Memory | `hardware_system_memory_mem_available_kilobytes`, `hardware_system_memory_mem_total_kilobytes` |
| 15 | Page Faults | `mongodb_extra_info_page_faults` |
| 16 | Query Executor | `mongodb_metrics_queryExecutor_scanned`, `mongodb_metrics_queryExecutor_scannedObjects` |
| 17 | Network | `mongodb_network_bytesIn`, `mongodb_network_bytesOut`, `mongodb_network_numRequests` |
| 18 | Process Memory | `mongodb_mem_resident`, `mongodb_mem_virtual` |
| 19 | Cache Ratios | computed WT cache fill and dirty fill ratios |
| 20 | Process CPU | `hardware_process_cpu_{user,kernel}_milliseconds` |

Metric and label names follow the
[Atlas Prometheus integration reference](https://www.mongodb.com/docs/atlas/tutorial/prometheus-integration/).
The rules use the labels Atlas attaches to every series: `group_id`,
`cl_name`, `rs_nm`, `rs_state` (1 = PRIMARY, 2 = SECONDARY), `node_type`,
`process_port`, `region`, and `availability_zone`. Hardware series repeat per
`process_port` on a host, so host-level rules de-duplicate them; keep
`process_port` (do not `labeldrop` it) or sharded-cluster series collide.

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

Custom namespace and Performance Advisor gauges should include `cl_name`,
`namespace`, `database`, and `collection` labels. The recording rules also
preserve `job`, `environment`, `region`, and `availability_zone` when those
labels are present.

> **Metric availability note:** Atlas Prometheus metric availability can vary
> by Atlas version, project settings, and whether host-measurement series are
> exposed in the Prometheus surface. Rules produce empty series when the
> underlying metrics are not present; `AtlasCoreMetricsMissing` flags this for
> the core inputs. Oplog churn has no documented Prometheus metric and is
> usually empty. Namespace and Performance Advisor rules also produce empty
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
> how to scope them with a `node_type` / `rs_state` label matcher.

Analytics nodes usually need more relaxed latency, CPU, and query-targeting
thresholds because they are outside the primary application read/write path.
The shipped alerts keep strict thresholds on `ELECTABLE` nodes; duplicate the
same rules with `node_type="ANALYTICS"` and looser thresholds if analytics
node alerting is required.

Every node-level alert includes a `context` annotation with `cl_name`,
`rs_nm`, `instance`, `node_type`, `rs_state`, `availability_zone`, and
`region`, all taken from the Atlas labels. Each alert also carries a `signal`
label (e.g. `disk_usage`, `cpu`) that Alertmanager uses to let a critical
alert suppress only its own warning counterpart.

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
mongodb_namespace_slow_queries_total{cl_name="...", namespace="db.collection", database="db", collection="collection"}
mongodb_namespace_p95_execution_time_ms{cl_name="...", namespace="db.collection", database="db", collection="collection"}
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
atlas_performance_advisor_index_recommendations{cl_name="...", namespace="db.collection", database="db", collection="collection"}
atlas_performance_advisor_unused_indexes{cl_name="...", namespace="db.collection", database="db", collection="collection"}
atlas_performance_advisor_redundant_indexes{cl_name="...", namespace="db.collection", database="db", collection="collection"}
```

Recommended triage flow:

1. Prometheus fires a latency or query-targeting alert.
2. Atlas Namespace Insights identifies the hot collection.
3. Atlas Query Profiler identifies the slow query shape.
4. Performance Advisor surfaces the index fix.
5. Prometheus confirms that metrics return to baseline.

### Monitoring-health alerts (`atlas_meta_alerting_rules.yml`)

The Atlas alerts above only fire if their input series exist. When a scrape
fails or a metric name does not match, they go quiet instead of failing. These
alerts catch that:

| Alert | Fires when |
|-------|------------|
| `Watchdog` | Always. Route to an external dead man's switch; silence means the pipeline is broken. |
| `AtlasScrapeTargetDown` | An Atlas target fails to scrape for 5m (auth, group ID, access list). |
| `AtlasScrapeTargetsMissing` | Service discovery returns no Atlas targets for 10m. |
| `AtlasServiceDiscoveryFailing` | Atlas discovery requests keep failing. |
| `AtlasCoreMetricsMissing` | Targets are up but core rule inputs are absent (metric-name / relabel mismatch). |
| `PrometheusRuleEvaluationFailures` | Any rule group fails to evaluate. |
| `PrometheusNotificationsFailing` / `AlertmanagerDown` / `AlertmanagerNotificationsFailing` | Alerts cannot be delivered. |

The Atlas job-name regex in this file must match the job names in
`prometheus*.yml`. Both configs also scrape Prometheus and Alertmanager
themselves to feed these alerts.

## Testing

```bash
promtool check rules atlas_*_rules.yml
promtool test rules tests/atlas_rules.test.yml
amtool check-config alertmanager.yml
```

CI runs the same checks (plus `promtool check config`) on every push.

## Verifying against a live cluster

Once Prometheus is scraping a real Atlas project, use these checks to
confirm the metrics assumed by the recording and alerting rules actually
land. Run each query from the Prometheus UI (<http://localhost:9090/graph>)
or via the HTTP API.

1. **Target is up and authenticated**

   ```promql
   up{job=~"mongodb_atlas_project|mongodb_atlas_.*"}
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

3. **Host (hardware) metrics are present**:

   ```promql
   hardware_system_cpu_user_milliseconds
   hardware_platform_num_logical_cpus
   hardware_disk_metrics_disk_space_used_bytes
   hardware_system_memory_mem_available_kilobytes
   hardware_process_cpu_user_milliseconds
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
   count by (cl_name, rs_nm, rs_state, instance, process_port, node_type, availability_zone, region) (mongodb_up)
   ```

   `rs_state` must be `1` on the primary and `2` on secondaries; the
   replication-lag, oplog-window, and headroom rules depend on it.

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

## Alertmanager

Alertmanager starts with the rest of the stack, and both Prometheus configs
send alerts to `alertmanager:9093`. `alertmanager.yml` provides:

- **Routing:** `Watchdog` → `deadmansswitch`, `severity=critical` → `pager`,
  `severity=warning` → `ticket`.
- **Inhibition:** a critical alert suppresses its warning counterpart on the
  same target, and `AtlasScrapeTargetDown` suppresses the other Atlas alerts
  for that node.

The receivers are **placeholders that drop alerts**. Wire them to real
integrations (PagerDuty, Slack, email, webhook, ...) before relying on it.

## References

- [Atlas Prometheus integration](https://www.mongodb.com/docs/atlas/tutorial/prometheus-integration/)
- [Prometheus configuration reference](https://prometheus.io/docs/prometheus/latest/configuration/configuration/)
- [Prometheus recording rules](https://prometheus.io/docs/prometheus/latest/configuration/recording_rules/)
- [Prometheus alerting rules](https://prometheus.io/docs/prometheus/latest/configuration/alerting_rules/)
