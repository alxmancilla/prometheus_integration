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

**Write-heavy nodes:** updates and deletes scan documents but return none,
so the ratio runs high on nodes that mostly write. Before hunting for
indexes, check the read/write mix (`node:mongodb_opcounters:rate5m` by `op`).
If writes dominate, check that update and delete filters use an index (Query
Profiler shows `docsExamined` for writes too); a high ratio from targeted
writes is harmless.

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

**Alerts:** `AtlasDiskUsageHigh` (>75%), `AtlasDiskUsageCritical` (>95%),
`AtlasDiskWillFillIn24h` (6h trend reaches full within 24h, disk >50% used).

**Meaning:** The data disk is filling up. Atlas can block writes when the
disk is full. Storage auto-scaling acts at about 90%, so the critical alert
means auto-scaling is off, at its maximum size, or not keeping up.

**Investigate:**
- Disk growth rate in the Hardware Metrics dashboard.
- Atlas → Collections: largest collections and indexes; unused indexes.
- Oplog size settings and any large bulk loads.

**Mitigate:** Enable storage auto-scaling (or raise its maximum) or increase disk size; drop unused
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

## replication-lag

**Alerts:** `AtlasReplicationLagHigh` (>60 s), `AtlasReplicationLagCritical` (>5 min).

**Meaning:** A secondary is behind the primary. Writes with `w: "majority"`
wait longer, reads from secondaries return stale data, and failover to this
node would roll back or lose recent writes. The value comes from two
separate scrapes, so it can be off by up to one scrape interval (60 s).

**Investigate:**
- Disk I/O and CPU on the lagging secondary (the usual bottleneck).
- Analytics or other heavy reads routed to that secondary.
- Large write bursts or bulk loads on the primary (opcounters, oplog churn).
- Network between regions for multi-region clusters.

**Mitigate:** Move analytics reads to analytics nodes, throttle bulk writes,
or scale the tier or disk IOPS. Watch `AtlasReplicationHeadroomLow`: if lag
keeps growing, the secondary will fall off the oplog.

## replication-headroom

**Alerts:** `AtlasReplicationHeadroomLow` (<12 h), `AtlasReplicationHeadroomCritical` (<1 h).

**Meaning:** Time left before the secondary falls off the oplog: its last
applied entry minus the oldest entry still in the primary's oplog. At zero,
the secondary can no longer catch up and needs a full initial sync.

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

## wiredtiger-cache

**Alerts:** `AtlasWiredTigerDirtyCacheHigh` (dirty >10%),
`AtlasWiredTigerDirtyCacheCritical` (dirty >20%), `AtlasWiredTigerCacheFull`
(fill >95%).

**Meaning:** WiredTiger can't evict pages fast enough. Past ~20% dirty or
~95% full, application threads are drafted into eviction, so every
operation gets slower. High dirty data usually means disk can't keep up with
writes; a full cache means the working set doesn't fit in memory.

**Investigate:**
- Disk write latency and IOPS on the same node (dirty cache).
- Write volume and bulk loads (opcounters, oplog churn).
- Page faults, query targeting, and collection scans pulling cold data in
  (cache fill).

**Mitigate:** Throttle bulk writes, fix collection scans, add disk IOPS, or
scale to a tier with more RAM.

## execution-tickets

**Alerts:** `AtlasExecutionTicketsExhausted` (no read or write tickets available for 5 min).

**Meaning:** MongoDB caps how many operations run at once with read and
write tickets; on 7.0+ the cap adjusts automatically. With none available,
new operations wait in a queue and latency rises sharply. This is the
saturation signal to use on MongoDB 7.0+; the lock-queue alerts below cover
older versions.

**Investigate:** Long-running operations (Atlas → Real Time Performance
Panel), CPU, disk latency, WiredTiger cache pressure, and query targeting.

**Mitigate:** Kill runaway operations, fix inefficient queries, or scale
the tier.

## lock-queue

**Alerts:** `AtlasQueuedReadersOrWriters` (queue growing), `AtlasQueuedReadersOrWritersCritical` (>10 queued).
Most useful before MongoDB 7.0; on 7.0+ prefer [execution-tickets](#execution-tickets).

**Meaning:** Operations are waiting for execution tickets or locks; the
node is overloaded.

**Investigate:** CPU, disk latency, long-running operations (Atlas → Real
Time Performance Panel), and index builds or collection-level operations.

**Mitigate:** Kill runaway operations, fix inefficient queries, or scale
the tier.

## elections

**Alerts:** `AtlasPrimaryElectionDetected` (info: a new primary in the last 15 min),
`AtlasFrequentPrimaryElections` (critical: more than one election in 1 h).

`AtlasPrimaryElectionDetected` is info-only and Alertmanager mutes it during
the `atlas-maintenance` time interval in `alertmanager.yml`. Set that
interval to the project's maintenance window (Atlas → Project Settings →
Maintenance Window). For unplanned work such as a tier change, add a
silence: `amtool silence add alertname=AtlasPrimaryElectionDetected cl_name=<cluster> --duration=2h`.

**Meaning:** The replica set changed primary. A single election during
Atlas maintenance is normal; repeated elections are not.

**Investigate:** Atlas Activity Feed (maintenance, auto-scaling, test
failover); node health, CPU, and network around the election time.

**Mitigate:** Confirm applications reconnected (retryable writes/reads
enabled). For repeated elections, open a case with MongoDB Support.

## cpu

**Alerts:** `AtlasCpuSaturationHigh` (>80%), `AtlasCpuSaturationCritical` (>90%).

**Meaning:** Normalized host CPU, excluding steal, is saturated; latency
will rise. Steal has its own alert ([cpu-steal](#cpu-steal)).

**Investigate:** Process CPU vs system CPU, query targeting, opcounters
trend, and expensive aggregations in the Query Profiler.

**Mitigate:** Fix inefficient queries, spread reads to secondaries where
appropriate, or scale the tier (enable compute auto-scaling).

## cpu-steal

**Alert:** `AtlasCpuStealHigh` (>20% for 15 min).

**Meaning:** The hypervisor is giving this node's CPU time to other
tenants. On burstable tiers (M10/M20) this is how running out of CPU burst
credits shows up: the node is throttled even if MongoDB isn't busy. On M30+
sustained steal is rare and points to a noisy host.

**Investigate:** The tier, and whether CPU (user + kernel) was high before
steal climbed, which means the credits were spent by real load.

**Mitigate:** On M10/M20, scale to M30+ (no burst credits) or reduce load.
On M30+, if it persists, open a case with MongoDB Support.

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

**Alert:** `AtlasCoreMetricsMissing`, per job (one job per project with
the org-wide sync). The job's targets are up but metrics the rules depend on
are absent. Check `metric_relabel_configs` keep/drop regexes and
compare metric names against the Atlas Prometheus integration reference.

### rule-evaluation-failures

**Alert:** `PrometheusRuleEvaluationFailures`. Prometheus → Status → Rules
shows the failing rule and error. Usually a many-to-many match after a label
change; run `promtool test rules tests/atlas_rules.test.yml`.

### notifications-failing

**Alerts:** `PrometheusNotificationsFailing`, `AlertmanagerDown`,
`AlertmanagerNotificationsFailing`. Alerts are not being delivered.
Check `docker compose ps`, Alertmanager logs, and receiver credentials.
