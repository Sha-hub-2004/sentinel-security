import time
import random
import sys
import httpx

API_BASE_URL = "http://localhost:8000/ingest"

SERVICES = ["auth-service", "payment-service", "user-db-cluster", "notification-dispatcher"]
QUEUES = ["orders-queue", "emails-queue", "sms-dispatch-queue", "transcode-jobs"]
HOSTS = ["production-web-01", "production-app-02", "production-db-replica"]

print("🚀 Sentinel Telemetry Simulation Service Starting...")
print(f"Targeting FastAPI ingestion endpoints at: {API_BASE_URL}")
print("Press Ctrl+C to terminate the simulator.\n")

client = httpx.Client(timeout=5.0)

def post_metric(endpoint: str, payload: dict):
    url = f"{API_BASE_URL}/{endpoint}"
    try:
        res = client.post(url, json=payload)
        if res.status_code in [200, 201]:
            print(f"  [Ingest Success] Posted to {endpoint}: {payload.get('service_name') or payload.get('queue_name') or payload.get('host_name')}")
        else:
            print(f"  ❌ [Ingest Failure] {endpoint} returned status {res.status_code}: {res.text}")
    except Exception as e:
        print(f"  ❌ [Connection Error] Failed to connect to {url}: {e}")

iteration = 0

try:
    while True:
        iteration += 1
        print(f"\n--- Generating telemetry batch #{iteration} ---")
        
        # Determine if we are injecting anomalies this iteration
        # Inject anomalies every 5th iteration
        inject_anomaly = (iteration % 5 == 0)
        
        # 1. API HEALTH METRICS
        for svc in SERVICES:
            if inject_anomaly and svc == "payment-service":
                # High Latency anomaly
                payload = {
                    "service_name": svc,
                    "url": "https://api.sentinel-monitor.io/v1/payments/checkout",
                    "status_code": 200,
                    "response_time_ms": round(random.uniform(2500, 4200), 2)
                }
                print(f"🔥 [Inject Anomaly] Spiking latency on '{svc}'...")
            elif inject_anomaly and svc == "user-db-cluster":
                # Severe server outage anomaly
                payload = {
                    "service_name": svc,
                    "url": "https://db.sentinel-monitor.io/v1/users/query",
                    "status_code": 503,
                    "response_time_ms": round(random.uniform(100, 300), 2)
                }
                print(f"🔥 [Inject Anomaly] Raising HTTP 503 Outage on '{svc}'...")
            else:
                # Normal healthy readings
                payload = {
                    "service_name": svc,
                    "url": f"https://api.sentinel-monitor.io/v1/{svc.replace('-','/')}/health",
                    "status_code": 200,
                    "response_time_ms": round(random.uniform(35, 180), 2)
                }
            post_metric("api_health", payload)
            
        # 2. QUEUE METRICS
        for q in QUEUES:
            if inject_anomaly and q == "emails-queue":
                # Orphaned queue with backlog
                payload = {
                    "queue_name": q,
                    "total_messages": random.randint(350, 450),
                    "consumers": 0,
                    "unacked_messages": random.randint(150, 220)
                }
                print(f"🔥 [Inject Anomaly] Crashing consumers & backing up messages on '{q}'...")
            elif inject_anomaly and q == "orders-queue":
                # High congestion backlog
                payload = {
                    "queue_name": q,
                    "total_messages": random.randint(800, 1200),
                    "consumers": 5,
                    "unacked_messages": random.randint(550, 650)
                }
                print(f"🔥 [Inject Anomaly] Flooding unacked backlog on '{q}'...")
            else:
                # Normal healthy readings
                payload = {
                    "queue_name": q,
                    "total_messages": random.randint(0, 35),
                    "consumers": random.randint(3, 8),
                    "unacked_messages": random.randint(0, 4)
                }
            post_metric("queue_metrics", payload)
            
        # 3. SERVER HARDWARE HEALTH
        for host in HOSTS:
            if inject_anomaly and host == "production-web-01":
                # CPU / Memory exhaustion
                payload = {
                    "host_name": host,
                    "ip_address": "10.0.1.15",
                    "cpu_usage_pct": round(random.uniform(96.0, 99.8), 2),
                    "memory_usage_pct": round(random.uniform(95.5, 98.2), 2),
                    "disk_usage_pct": 82.4
                }
                print(f"🔥 [Inject Anomaly] Saturating CPU & RAM on '{host}'...")
            else:
                # Normal healthy readings
                payload = {
                    "host_name": host,
                    "ip_address": f"10.0.1.{random.randint(15, 30)}",
                    "cpu_usage_pct": round(random.uniform(12.0, 48.0), 2),
                    "memory_usage_pct": round(random.uniform(35.0, 62.0), 2),
                    "disk_usage_pct": 54.2
                }
            post_metric("server_health", payload)
            
        # 4. SYSTEM EVENT LOGGING
        log_choices = [
            ("INFO", "User login credentials validated successfully"),
            ("INFO", "Database cache flushed and optimized"),
            ("INFO", "Outgoing payment webhook acknowledged"),
            ("DEBUG", "Verbose garbage collector sweep finished in 12ms")
        ]
        
        # Send a standard healthy log
        lvl, msg = random.choice(log_choices)
        post_metric("system_log", {
            "service_name": random.choice(SERVICES),
            "log_level": lvl,
            "message": msg
        })
        
        # Send an anomaly log if triggered
        if inject_anomaly:
            print("🔥 [Inject Anomaly] Logging critical security exception...")
            post_metric("system_log", {
                "service_name": "auth-service",
                "log_level": "CRITICAL",
                "message": "Security lockout triggered! IP 198.51.100.42 exceeded 50 login attempts in 1 minute."
            })
            post_metric("system_log", {
                "service_name": "payment-service",
                "log_level": "ERROR",
                "message": "Gateway Connection Refused: SSL Handshake timeout with master card clearinghouse api."
            })

        print("------------------------------------------")
        print("Sleeping for 10 seconds before next wave...")
        time.sleep(10)

except KeyboardInterrupt:
    print("\n👋 Telemetry simulation stopped. Thank you for using Sentinel!")
    client.close()
    sys.exit(0)
