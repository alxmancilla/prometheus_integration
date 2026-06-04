Create a new directory with a Prometheus configuration and a Dockerfile like this:

FROM prom/prometheus
ADD prometheus.yml /etc/prometheus/

Now build and run it:
docker build -t my-prometheus .
docker run -p 9090:9090 my-prometheus

A more advanced option is to render the configuration dynamically on start with some tooling or even have a daemon update it periodically.

On your browser, go to Prometheus Dashboard through: http://localhost:9090/.   (use your local IP address instead)

Prometheus will ask for your login information. This should be the username and password you generated before

Once on Prometheus’ dashboard, validate if you are seeing Atlas clusters in your project:


Setting Up Grafana. 

https://prometheus.io/docs/visualization/grafana/

This is a straightforward process as the bulk of work has been done above. So, once Grafana is installed, it will use your Prometheus instance as its data source. Again, we will only integrate Grafana with Prometheus, however, how to build Grafana graphs is not in the scope of this guide.

We will use Docker images as well.

docker run -d --name=grafana -p 3000:3000 grafana/grafana-enterprise     ## recommended

docker run -d --name=grafana -p 3000:3000 grafana/grafana-enterprise:13.0.2-ubuntu


Go to http://localhost:3000

Initial username and password are admin/admin. (admin/4dm1n4dm1n)

Integrate Grafana with Prometheus: This is setting up Prometheus as a Data Source for Grafana

Click on Settings → Configuration → Data sources
Choose Prometheus (Usually default)
Configure Prometheus Data Source. Here the important information you need:

URL: http://localhost:9090 (you can use local host, but it may be problematic, so use your local IP instead)

Access: should remain Default





Essential Metrics to Monitor

Focus on these key metric categories:

# Connection metrics  
mongodb_atlas_connections_current  
mongodb_atlas_connections_available  
  
# Operation metrics  
mongodb_atlas_opcounters_total{type="query|insert|update|delete"}  
  
# Replication lag  
mongodb_atlas_replication_lag_seconds  
  
# Disk and memory  
mongodb_atlas_disk_partition_utilization_percent  
mongodb_atlas_memory_resident_megabytes  
  
# Query performance  
mongodb_atlas_query_targeting_scanned_objects_per_returned  



Set Up Meaningful Alerts

- High Connection Utilization
- Replication Lag High
- Disk Space Low


