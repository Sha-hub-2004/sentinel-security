from prometheus_client import Counter, CollectorRegistry

# Standard Prometheus metrics registry
REGISTRY = CollectorRegistry()

INGEST_REQUESTS_TOTAL = Counter(
    "sentinel_ingest_requests_total",
    "Total ingestion requests processed",
    ["endpoint", "status"],
    registry=REGISTRY
)

ALERTS_TRIGGERED_TOTAL = Counter(
    "sentinel_alerts_triggered_total",
    "Total alerts generated",
    ["source", "severity"],
    registry=REGISTRY
)

ANOMALIES_DETECTED_TOTAL = Counter(
    "sentinel_anomalies_detected_total",
    "Total anomalies detected",
    ["source", "detection_method"],
    registry=REGISTRY
)
