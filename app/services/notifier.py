import time
import smtplib
from typing import Dict, Tuple, Optional
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from app.core.config import settings
from app.logger import get_logger
from app.models import Alert

logger = get_logger("notifier")

# In-memory dictionary to store last sent timestamps for alert throttling
# Key: (source, title), Value: timestamp (float)
_last_sent_cache: Dict[Tuple[str, str], float] = {}


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((httpx.HTTPError, TimeoutError)),
    reraise=True
)
async def send_slack_webhook(payload: dict) -> None:
    """Send alert payload to Slack with exponential retries."""
    if not settings.SLACK_WEBHOOK_URL:
        return
    async with httpx.AsyncClient() as client:
        res = await client.post(settings.SLACK_WEBHOOK_URL, json=payload, timeout=5.0)
        res.raise_for_status()


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((httpx.HTTPError, TimeoutError)),
    reraise=True
)
async def send_teams_webhook(payload: dict) -> None:
    """Send alert payload to Microsoft Teams with exponential retries."""
    if not settings.TEAMS_WEBHOOK_URL:
        return
    async with httpx.AsyncClient() as client:
        res = await client.post(settings.TEAMS_WEBHOOK_URL, json=payload, timeout=5.0)
        res.raise_for_status()


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((smtplib.SMTPException, ConnectionError)),
    reraise=True
)
def send_email_smtp(subject: str, html_body: str) -> None:
    """Send alert email via SMTP with exponential retries."""
    if not (settings.SMTP_HOST and settings.SMTP_USER and settings.SMTP_PASSWORD and settings.ALERT_EMAIL_RECIPIENT):
        return
    
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.SMTP_USER
    msg["To"] = settings.ALERT_EMAIL_RECIPIENT
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
        server.starttls()
        server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.sendmail(settings.SMTP_USER, settings.ALERT_EMAIL_RECIPIENT, msg.as_string())


def is_throttled(source: str, title: str) -> bool:
    """Check if the alert should be throttled (rate-limited)."""
    now = time.time()
    key = (source, title)
    last_sent = _last_sent_cache.get(key, 0.0)
    if now - last_sent < settings.ALERT_THROTTLE_WINDOW:
        return True
    _last_sent_cache[key] = now
    return False


async def dispatch_enterprise_alert(alert: Alert) -> bool:
    """Evaluate and dispatch alerts to Slack, Teams, and Email, applying throttling and retry rules."""
    # Filter: Only trigger for CRITICAL alerts, queue overflow (congestions), or anomaly alerts
    is_critical = alert.severity == "CRITICAL"
    is_queue_overflow = "congestion" in alert.title.lower() or "overflow" in alert.title.lower()
    is_persistent_anomaly = "persistent" in alert.title.lower() or "anomaly" in alert.title.lower()

    if not (is_critical or is_queue_overflow or is_persistent_anomaly):
        logger.info(f"Alert ID {alert.id} ({alert.severity}) filtered out from enterprise notification channels.")
        return False

    # Apply Throttling
    if is_throttled(alert.source, alert.title):
        logger.warning(f"Alert Storm Prevented! Throttling notification for alert: [{alert.source}] {alert.title}")
        return False

    # Dispatch to Slack
    if settings.SLACK_WEBHOOK_URL:
        try:
            color = "#FF0000" if alert.severity == "CRITICAL" else "#FFA500"
            payload = {
                "attachments": [
                    {
                        "color": color,
                        "title": f"🚨 [{alert.severity}] SOC Alert from {alert.source.upper()}",
                        "text": f"*{alert.title}*\n{alert.description}",
                        "fields": [
                            {"title": "Incident ID", "value": str(alert.id), "short": True},
                            {"title": "Timestamp", "value": str(alert.timestamp), "short": True},
                        ],
                    }
                ]
            }
            await send_slack_webhook(payload)
            logger.info(f"Successfully dispatched Slack alert for Alert ID {alert.id}")
        except Exception:
            logger.exception(f"Failed to dispatch Slack alert for Alert ID {alert.id} after retries")

    # Dispatch to Teams
    if settings.TEAMS_WEBHOOK_URL:
        try:
            payload = {
                "@type": "MessageCard",
                "@context": "http://schema.org/extensions",
                "themeColor": "FF0000" if alert.severity == "CRITICAL" else "FFA500",
                "summary": f"SOC Alert: {alert.title}",
                "sections": [
                    {
                        "activityTitle": f"🛡️ [{alert.severity}] Security Incident: {alert.source.upper()}",
                        "activitySubtitle": f"Timestamp: {alert.timestamp}",
                        "facts": [
                            {"name": "Alert ID", "value": str(alert.id)},
                            {"name": "Incident", "value": alert.title},
                            {"name": "Description", "value": alert.description}
                        ],
                        "markdown": True
                    }
                ]
            }
            await send_teams_webhook(payload)
            logger.info(f"Successfully dispatched Microsoft Teams alert for Alert ID {alert.id}")
        except Exception:
            logger.exception(f"Failed to dispatch Microsoft Teams alert for Alert ID {alert.id} after retries")

    # Dispatch to Email
    if settings.SMTP_HOST and settings.SMTP_USER and settings.SMTP_PASSWORD and settings.ALERT_EMAIL_RECIPIENT:
        try:
            subject = f"🚨 [{alert.severity}] {alert.title}"
            severity_color = "#dc3545" if alert.severity == "CRITICAL" else "#ffc107"
            html = f"""
            <html>
              <body style="font-family: Arial, sans-serif; background-color: #f8f9fa; padding: 20px; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff; border: 1px solid #dee2e6; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                  <div style="background-color: {severity_color}; padding: 15px; text-align: center; color: #ffffff;">
                    <h2 style="margin: 0; font-size: 22px;">Security Alert Notification</h2>
                  </div>
                  <div style="padding: 20px;">
                    <p style="font-size: 16px; font-weight: bold; margin-top: 0;">Severity: <span style="color: {severity_color};">{alert.severity}</span></p>
                    <hr style="border: 0; border-top: 1px solid #dee2e6;" />
                    <h3 style="color: #333; margin-top: 15px;">{alert.title}</h3>
                    <p style="line-height: 1.5; font-size: 14px; color: #555;">{alert.description}</p>
                  </div>
                </div>
              </body>
            </html>
            """
            # Run SMTP blocking call inside an async-compatible context (standard thread pool or directly if background task)
            send_email_smtp(subject, html)
            logger.info(f"Successfully dispatched Email alert for Alert ID {alert.id}")
        except Exception:
            logger.exception(f"Failed to dispatch Email alert for Alert ID {alert.id} after retries")
            
    return True
