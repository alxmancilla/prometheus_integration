FROM prom/prometheus
COPY prometheus.yml /etc/prometheus/
COPY atlas_recording_rules.yml /etc/prometheus/rules/atlas_recording_rules.yml
COPY atlas_alerting_rules.yml /etc/prometheus/rules/atlas_alerting_rules.yml
