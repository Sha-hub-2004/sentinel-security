from typing import Any, Dict, Optional
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import httpx
from sqlmodel.ext.asyncio.session import AsyncSession
from app.models import Alert
from app.core.config import settings
from app.logger import get_logger

logger = get_logger("alert_engine")


async def evaluate_metric(source: str, data: Dict[str, Any], session: AsyncSession) -> Optional[Alert]:
    """Evaluate incoming metric against standard policy rules and trigger alerts.

    Returns the generated Alert object if triggered, otherwise None.
    """
    alert_triggered = False
    severity = "LOW"
    title = ""
    description = ""

    try:
        if source == "api_health":
            service_name = data.get("service_name", "Unknown Service")
            url = data.get("url", "")
            status_code = int(data.get("status_code", 200))
            response_time = float(data.get("response_time_ms", 0.0))

            if status_code >= 500:
                alert_triggered = True
                severity = "CRITICAL"
                title = f"API Service Failure: {service_name}"
                description = f"Service '{service_name}' on {url} is failing with HTTP {status_code}."
            elif status_code >= 400:
                alert_triggered = True
                severity = "MEDIUM"
                title = f"API Client Error: {service_name}"
                description = f"Service '{service_name}' on {url} returned HTTP {status_code}."
            elif response_time > 2000.0:
                alert_triggered = True
                severity = "MEDIUM"
                title = f"API Latency Spike: {service_name}"
                description = f"Service '{service_name}' response latency is high: {response_time:.2f}ms (threshold: 2000ms)."

        elif source == "queue_metrics":
            queue_name = data.get("queue_name", "Unknown Queue")
            total_messages = int(data.get("total_messages", 0))
            consumers = int(data.get("consumers", 0))
            unacked_messages = int(data.get("unacked_messages", 0))

            if unacked_messages > 500:
                alert_triggered = True
                severity = "CRITICAL"
                title = f"Queue Congestion: {queue_name}"
                description = f"Queue '{queue_name}' is congested with {unacked_messages} unacknowledged messages."
            elif unacked_messages > 100:
                alert_triggered = True
                severity = "MEDIUM"
                title = f"Queue Backlog: {queue_name}"
                description = f"Queue '{queue_name}' backlog is high: {unacked_messages} unacknowledged messages."
            
            if consumers == 0 and total_messages > 0:
                alert_triggered = True
                severity = "CRITICAL"
                title = f"Orphaned Queue: {queue_name}"
                description = f"Queue '{queue_name}' has {total_messages} messages but NO active consumers processing them."

        elif source == "server_health":
            host_name = data.get("host_name", "Unknown Host")
            cpu_usage = float(data.get("cpu_usage_pct", 0.0))
            memory_usage = float(data.get("memory_usage_pct", 0.0))
            disk_usage = float(data.get("disk_usage_pct", 0.0))

            # CPU Rules
            if cpu_usage > 95.0:
                alert_triggered = True
                severity = "CRITICAL"
                title = f"CPU Exhaustion: {host_name}"
                description = f"Host '{host_name}' CPU utilization is critical: {cpu_usage:.1f}%."
            elif cpu_usage > 85.0:
                alert_triggered = True
                severity = "MEDIUM"
                title = f"High CPU Load: {host_name}"
                description = f"Host '{host_name}' CPU utilization is high: {cpu_usage:.1f}%."

            # RAM Rules
            if memory_usage > 95.0:
                alert_triggered = True
                severity = "CRITICAL"
                title = f"Memory Exhaustion: {host_name}"
                description = f"Host '{host_name}' Memory utilization is critical: {memory_usage:.1f}%."
            elif memory_usage > 85.0:
                alert_triggered = True
                severity = "MEDIUM"
                title = f"High Memory Load: {host_name}"
                description = f"Host '{host_name}' Memory utilization is high: {memory_usage:.1f}%."

            # Disk Rules
            if disk_usage > 90.0:
                alert_triggered = True
                severity = "MEDIUM"
                title = f"Low Disk Capacity: {host_name}"
                description = f"Host '{host_name}' disk space is running out: {disk_usage:.1f}% utilized."

        elif source == "system_log":
            service_name = data.get("service_name", "Unknown Service")
            log_level = str(data.get("log_level", "INFO")).upper()
            message = data.get("message", "")

            if log_level == "CRITICAL":
                alert_triggered = True
                severity = "CRITICAL"
                title = f"Critical Event Logged: {service_name}"
                description = f"Service '{service_name}' logged a CRITICAL exception: '{message}'"
            elif log_level == "ERROR":
                alert_triggered = True
                severity = "MEDIUM"
                title = f"Error Event Logged: {service_name}"
                description = f"Service '{service_name}' logged an ERROR: '{message}'"

        policy_alert_obj = None
        if alert_triggered:
            policy_alert_obj = Alert(
                source=source,
                severity=severity,
                title=title,
                description=description,
            )
            session.add(policy_alert_obj)
            await session.commit()
            await session.refresh(policy_alert_obj)
            logger.warning(f"🚨 ALERT TRIGGERED [{severity}]: {title} - {description}")
            
            try:
                from app.core.metrics import ALERTS_TRIGGERED_TOTAL
                ALERTS_TRIGGERED_TOTAL.labels(source=source, severity=severity).inc()
            except Exception:
                pass

            await dispatch_notifications(policy_alert_obj)
            try:
                import asyncio
                from app.services.elasticsearch_client import send_to_elasticsearch
                asyncio.create_task(send_to_elasticsearch("alerts", policy_alert_obj.dict()))
            except Exception:
                pass
            
            try:
                from app.services.correlation import correlate_new_alert
                await correlate_new_alert(policy_alert_obj, session)
            except Exception:
                logger.exception("Failed to correlate policy alert")

        # Run anomaly detection
        try:
            from app.services.anomaly_detector import evaluate_anomalies
            resource_name = "Unknown"
            if source == "api_health":
                resource_name = data.get("service_name", "Unknown Service")
            elif source == "queue_metrics":
                resource_name = data.get("queue_name", "Unknown Queue")
            elif source == "server_health":
                resource_name = data.get("host_name", "Unknown Host")

            if resource_name != "Unknown":
                anomalies = await evaluate_anomalies(session, source, resource_name, data)
                for anomaly in anomalies:
                    anomaly_severity = "MEDIUM"
                    if anomaly.detection_method == "Z-Score" and abs(anomaly.score) > 4.0:
                        anomaly_severity = "CRITICAL"
                    
                    anomaly_alert = Alert(
                        source=source,
                        severity=anomaly_severity,
                        title=f"Anomaly: {anomaly.metric_name} on {resource_name}",
                        description=anomaly.description,
                    )
                    session.add(anomaly_alert)
                    await session.commit()
                    await session.refresh(anomaly_alert)
                    logger.warning(f"🚨 ANOMALY ALERT TRIGGERED [{anomaly_severity}]: {anomaly_alert.title} - {anomaly_alert.description}")
                    
                    try:
                        from app.core.metrics import ALERTS_TRIGGERED_TOTAL
                        ALERTS_TRIGGERED_TOTAL.labels(source=source, severity=anomaly_severity).inc()
                    except Exception:
                        pass

                    await dispatch_notifications(anomaly_alert)
                    try:
                        import asyncio
                        from app.services.elasticsearch_client import send_to_elasticsearch
                        asyncio.create_task(send_to_elasticsearch("alerts", anomaly_alert.dict()))
                    except Exception:
                        pass
                    
                    try:
                        from app.services.correlation import correlate_new_alert
                        await correlate_new_alert(anomaly_alert, session)
                    except Exception:
                        logger.exception("Failed to correlate anomaly alert")
        except Exception:
            logger.exception("Failed to run anomaly detection during metric evaluation")

        if policy_alert_obj:
            return policy_alert_obj

    except Exception:
        logger.exception(f"Error evaluating metrics for source: {source}")
    
    return None


async def dispatch_notifications(alert: Alert) -> None:
    """Route notifications to configured communication channels with retries and throttling."""
    from app.services.notifier import dispatch_enterprise_alert
    await dispatch_enterprise_alert(alert)
