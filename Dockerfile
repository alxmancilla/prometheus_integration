FROM prom/prometheus:v3.16.0
COPY prometheus.yml /etc/prometheus/
COPY atlas_recording_rules.yml /etc/prometheus/rules/atlas_recording_rules.yml
COPY atlas_alerting_rules.yml /etc/prometheus/rules/atlas_alerting_rules.yml
COPY atlas_meta_alerting_rules.yml /etc/prometheus/rules/atlas_meta_alerting_rules.yml
