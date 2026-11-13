# Verifying against a live cluster

Back to the [README](../README.md).

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

