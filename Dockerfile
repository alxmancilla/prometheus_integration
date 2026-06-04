FROM prom/prometheus
ADD prometheus.yml /etc/prometheus/
ADD alert.rules.yml /etc/prometheus/
