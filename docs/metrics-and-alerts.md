# Metrics, recording rules, and alerts

Reference for what the rule files compute and alert on. Back to the [README](../README.md).

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
| 8 | Global Lock Queue / Execution Tickets | `mongodb_globalLock_currentQueue_*`; `mongodb_wiredTiger_concurrentTransactions_*_available` or `mongodb_queues_execution_*_available` (7.0+) |
| 9 | Opcounters | `mongodb_opcounters_*` |
| 10 | Scan and Order | `mongodb_metrics_operation_scanAndOrder`, `mongodb_metrics_query_sort_spillToDisk` |
| 11 | Replication Safety | computed secondary lag, and headroom against the primary's oplog |
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

## Recording rules (`atlas_recording_rules.yml`)

Pre-aggregated series that dashboards and alerts query directly. Common
examples:

- `node:mongodb_oplatencies_reads:avg_usec` / `node:mongodb_oplatencies_writes:avg_usec` — average read/write latency
- `node:mongodb_query_targeting:ratio` — scanned objects per returned document
- `node:mongodb_disk_space_used:ratio` — disk usage ratio
- `node:mongodb_connections_utilization:ratio` — current / tier-limit connections, where Atlas exposes available connections
- `node:mongodb_oplog_window:seconds` — oplog window per node
- `node:mongodb_replication_lag:seconds` — how far each secondary is behind the primary
- `node:mongodb_replication_headroom:seconds` — time before a secondary falls off the primary's oplog
- `node:mongodb_tickets_available:count` — free read/write execution tickets (`op` label)
- `rs:mongodb_primary_elections:count1h` — elections per replica set
- `node:mongodb_wiredtiger_cache_fill:ratio` / `node:mongodb_wiredtiger_cache_dirty_fill:ratio` — WT cache ratios
- `cluster:mongodb_opcounters_total:rate5m` — total operation rate per cluster
- `namespace:mongodb_slow_queries:rate5m` — slow query rate by namespace when custom-exported
- `namespace:mongodb_p95_execution_time:ms` — P95 execution time by namespace when custom-exported
- `namespace:atlas_performance_advisor_index_recommendations:count` — index recommendations by namespace when custom-exported

## Alerting rules (`atlas_alerting_rules.yml`)

Grouped by signal, with warning + critical tiers where useful. Recommended
alerts are implemented with the requested starting thresholds:

| Group | Alerts |
|-------|--------|
| Query targeting | `AtlasQueryTargetingRatioHigh` (>100, 5m), `AtlasQueryTargetingRatioCritical` (>1000, 5m); both also require >1000 scanned docs/s |
| Read/write latency | `AtlasReadLatencyHigh` / `AtlasWriteLatencyHigh` (>100ms, 5m), critical variants (>250ms, 5m) |
| Disk usage | `AtlasDiskUsageHigh` (>75%, 5m), `AtlasDiskUsageCritical` (>90%, 5m) |
| Oplog window | `AtlasOplogWindowLow` (<24h, 5m), `AtlasOplogWindowCritical` (<1h, 10m) |
| Connections | `AtlasConnectionUtilizationHigh` (>80%, 5m), `AtlasConnectionUtilizationCritical` (>90%, 5m) |
| Replication lag | `AtlasReplicationLagHigh` (>60s, 5m), `AtlasReplicationLagCritical` (>5m, 5m) |
| WiredTiger cache | `AtlasWiredTigerDirtyCacheHigh` (dirty >10%, 10m), `AtlasWiredTigerDirtyCacheCritical` (dirty >20%, 5m), `AtlasWiredTigerCacheFull` (fill >95%, 10m) |
| Execution tickets (7.0+) | `AtlasExecutionTicketsExhausted` (no read or write tickets, 5m) |
| Replication headroom | `AtlasReplicationHeadroomLow` (<12h, 5m), `AtlasReplicationHeadroomCritical` (<1h, 5m) |
| System memory available | `AtlasSystemMemoryAvailableLow` (<75% of 7-day baseline, 10m), `AtlasSystemMemoryAvailableCritical` (<5%, 10m) |
| Page faults | `AtlasPageFaultsHigh` (>50/s, 5m), `AtlasPageFaultsCritical` (>100/s, 5m) |
| Queued readers/writers (pre-7.0) | `AtlasQueuedReadersOrWriters` (sustained queue growth, 5m), `AtlasQueuedReadersOrWritersCritical` (>10 queued readers or writers, 5m) |
| Primary election | `AtlasPrimaryElectionDetected` (any election in 15m), `AtlasFrequentPrimaryElections` (>1 election in 1h) |
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

Query-targeting alerts only fire while a node scans more than 1000
documents/s. On idle nodes, small background collection scans divided by
near-zero returned documents produce large but harmless ratios (observed:
100–145 on a demo cluster returning <1 doc/s). Tune the floor in
`atlas_alerting_rules.yml` to your workload.

Every alert has a `runbook_url` annotation pointing to its section in
[`runbooks.md`](runbooks.md). If you fork the repo, update the base
URL in both rule files (and the expected annotations in `tests/`).

Every node-level alert includes a `context` annotation with `cl_name`,
`rs_nm`, `instance`, `node_type`, `rs_state`, `availability_zone`, and
`region`, all taken from the Atlas labels. Each alert also carries a `signal`
label (e.g. `disk_usage`, `cpu`) that Alertmanager uses to let a critical
alert suppress only its own warning counterpart.

## Query Performance Signals

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

## Performance Advisor

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

## Monitoring-health alerts (`atlas_meta_alerting_rules.yml`)

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


## Alertmanager routing

`alertmanager.yml` provides:

- **Routing:** `Watchdog` → `deadmansswitch`, `severity=critical` → `pager`,
  `severity=warning` → `ticket`.
- **Inhibition:** a critical alert suppresses its warning counterpart on the
  same target, and `AtlasScrapeTargetDown` suppresses the other Atlas alerts
  for that node.

The receivers are **placeholders that drop alerts**. Wire them to real
integrations (PagerDuty, Slack, email, webhook, ...) before relying on it.
