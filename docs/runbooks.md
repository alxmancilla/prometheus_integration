# Atlas Alert Runbooks

One section per alert signal. Each alert in `atlas_alerting_rules.yml` and
`atlas_meta_alerting_rules.yml` links here through its `runbook_url`
annotation. The `context` annotation on node alerts gives the cluster
(`cl_name`), replica set (`rs_nm`), node, `node_type`, `rs_state`
(1 = primary, 2 = secondary), zone, and region.

General first steps for any Atlas alert:

1. Open the node in Atlas → Clusters → Metrics and confirm the signal.
2. Check Atlas → Project Activity Feed for maintenance, scaling, or failover
   events at the same time.
3. Check the Grafana dashboards in the **MongoDB Atlas** folder for related
   signals (CPU, cache, connections, opcounters) on the same node.

---

## query-targeting

**Alerts:** `AtlasQueryTargetingRatioHigh` (>100), `AtlasQueryTargetingRatioCritical` (>1000).
Both only fire while the node scans more than 1000 documents/s.

**Meaning:** Queries examine many more documents than they return, usually
because of a missing or unselective index.

**Investigate:**
- Atlas → Performance Advisor: suggested indexes for the node.
- Atlas → Query Insights / Namespace Insights: which collection has the
  most examined documents.
- Atlas → Query Profiler: slow query shapes and their `docsExamined`.
- Dashboard: compare `node:mongodb_queryexecutor_scanned_objects:rate5m`
  with `node:mongodb_documents_returned:rate5m`.

**Mitigate:** Create the suggested index (rolling build in Atlas), rewrite
the query to use an existing index, or add a projection/limit.

## read-latency / write-latency

**Alerts:** `AtlasReadLatencyHigh` / `AtlasWriteLatencyHigh` (>100 ms),
`AtlasReadLatencyCritical` / `AtlasWriteLatencyCritical` (>250 ms).

**Meaning:** Average server-side operation latency is high. Applications
are slowing down.

**Investigate:**
- Correlate with CPU, disk latency/IOPS, WiredTiger cache fill/dirty fill,
  and queued readers/writers on the same node.
- Query Profiler for the slow operations; Performance Advisor for indexes.
- Writes: check write concern, replication lag, and disk write latency.

**Mitigate:** Fix the offending queries or indexes; if resources are
saturated, scale the cluster tier or enable/adjust auto-scaling.

## disk-usage

**Alerts:** `AtlasDiskUsageHigh` (>75%), `AtlasDiskUsageCritical` (>90%).

**Meaning:** The data disk is filling up. Atlas can block writes when the
disk is full.

**Investigate:**
- Disk growth rate in the Hardware Metrics dashboard.
- Atlas → Collections: largest collections and indexes; unused indexes.
- Oplog size settings and any large bulk loads.

**Mitigate:** Enable storage auto-scaling or increase disk size; drop unused
indexes/collections; archive old data (Online Archive, TTL indexes).
Compaction only helps after large deletes.

## oplog-window

**Alerts:** `AtlasOplogWindowLow` (<24 h), `AtlasOplogWindowCritical` (<1 h). Secondaries only.

**Meaning:** The oplog covers too little time. A secondary that falls
behind longer than the window needs a full initial sync.

**Investigate:** Oplog churn (write volume), recent bulk writes or
migrations, and the configured oplog size / minimum retention.

**Mitigate:** Increase the oplog size or set a minimum oplog retention
window in the cluster's advanced settings; throttle bulk writes.

## replication-headroom

**Alerts:** `AtlasReplicationHeadroomLow` (<12 h), `AtlasReplicationHeadroomCritical` (<1 h).

**Meaning:** Oplog window minus the secondary's lag is shrinking; the
secondary is close to falling off the oplog.

**Investigate:** `node:mongodb_replication_lag:seconds` per secondary; CPU,
disk, and network on the lagging secondary; heavy write bursts on the
primary.

**Mitigate:** Reduce write pressure, increase oplog size, and resolve the
resource bottleneck on the secondary. Contact MongoDB Support if a
secondary falls off the oplog.

## connections

**Alerts:** `AtlasConnectionUtilizationHigh` (>80%), `AtlasConnectionUtilizationCritical` (>90%).

**Meaning:** The node is close to its connection limit for the tier. New
connections will be refused.

**Investigate:** Connection count trend; recent application deploys;
driver `maxPoolSize` × number of app instances; connection leaks
(connections that grow without falling).

**Mitigate:** Lower driver pool sizes or reuse clients; fix leaks; restart
leaking app instances; scale up the tier for a higher limit.

## system-memory

**Alerts:** `AtlasSystemMemoryAvailableLow` (<75% of the 7-day baseline),
`AtlasSystemMemoryAvailableCritical` (<5%).

**Meaning:** Available host memory is unusually low or nearly exhausted.

**Investigate:** WiredTiger cache fill, process resident memory, swap
activity (`node:mongodb_system_swap_out:rate5m`), connection count, and
large in-memory sorts or aggregations.

**Mitigate:** Reduce memory-heavy operations, lower connection count, or
scale up the tier.

## page-faults

**Alerts:** `AtlasPageFaultsHigh` (>50/s), `AtlasPageFaultsCritical` (>100/s).

**Meaning:** The working set does not fit in memory; reads go to disk.

**Investigate:** WiredTiger cache fill, disk read IOPS/latency, and recent
changes in query patterns or data volume.

**Mitigate:** Add indexes to reduce scanned data, trim the working set, or
scale up to a tier with more RAM.

## lock-queue

**Alerts:** `AtlasQueuedReadersOrWriters` (queue growing), `AtlasQueuedReadersOrWritersCritical` (>10 queued).

**Meaning:** Operations are waiting for execution tickets or locks; the
node is overloaded.

**Investigate:** CPU, disk latency, long-running operations (Atlas → Real
Time Performance Panel), and index builds or collection-level operations.

**Mitigate:** Kill runaway operations, fix inefficient queries, or scale
the tier.

## elections

**Alerts:** `AtlasPrimaryElectionDetected` (any role change in 15 min),
`AtlasFrequentPrimaryElections` (>1 change in 1 h).

**Meaning:** The replica set changed primary. A single election during
Atlas maintenance is normal; repeated elections are not.

**Investigate:** Atlas Activity Feed (maintenance, auto-scaling, test
failover); node health, CPU, and network around the election time.

**Mitigate:** Confirm applications reconnected (retryable writes/reads
enabled). For repeated elections, open a case with MongoDB Support.

## cpu

**Alerts:** `AtlasCpuSaturationHigh` (>80%), `AtlasCpuSaturationCritical` (>90%).

**Meaning:** Normalized host CPU is saturated; latency will rise.

**Investigate:** Process CPU vs system CPU, query targeting, opcounters
trend, and expensive aggregations in the Query Profiler.

**Mitigate:** Fix inefficient queries, spread reads to secondaries where
appropriate, or scale the tier (enable compute auto-scaling).

---

## Monitoring health

### watchdog

**Alert:** `Watchdog` — always firing by design. If your dead man's switch
stops receiving it, Prometheus, Alertmanager, or the path between them is
down. Check `docker compose ps` and the container logs.

### scrape-target-down

**Alert:** `AtlasScrapeTargetDown`. Prometheus cannot scrape an Atlas node,
so its alerts are blind.

- Prometheus → Status → Targets shows the error.
- `401`: wrong username or password (`secrets/atlas_password`), or the
  password was regenerated in Atlas.
- Timeout / connection refused: the Prometheus host's IP is not on the
  Atlas IP Access List, or the node is down.
- `permission denied` reading the secret: the file must be readable by
  UID 65534.

### scrape-targets-missing

**Alert:** `AtlasScrapeTargetsMissing`. Service discovery returned no
targets. Check the group ID in the discovery URL, that the Prometheus
integration is still enabled in Atlas, and that `0.0.0.0/0` was not added to
the IP Access List (Atlas disables the integration).

### service-discovery-failing

**Alert:** `AtlasServiceDiscoveryFailing`. Requests to the Atlas discovery
endpoint fail. Same checks as above; also test it directly:
`curl -u USER:PASS https://cloud.mongodb.com/prometheus/v1.0/groups/GROUP_ID/discovery`.

### core-metrics-missing

**Alert:** `AtlasCoreMetricsMissing`. Targets are up but metrics the rules
depend on are absent. Check `metric_relabel_configs` keep/drop regexes and
compare metric names against the Atlas Prometheus integration reference.

### rule-evaluation-failures

**Alert:** `PrometheusRuleEvaluationFailures`. Prometheus → Status → Rules
shows the failing rule and error. Usually a many-to-many match after a label
change; run `promtool test rules tests/atlas_rules.test.yml`.

### notifications-failing

**Alerts:** `PrometheusNotificationsFailing`, `AlertmanagerDown`,
`AlertmanagerNotificationsFailing`. Alerts are not being delivered.
Check `docker compose ps`, Alertmanager logs, and receiver credentials.
