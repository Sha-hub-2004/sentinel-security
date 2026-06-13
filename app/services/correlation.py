from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from app.models import Alert, AlertCorrelation
from app.logger import get_logger
from datetime import datetime, timedelta
from typing import Optional

logger = get_logger("correlation_engine")


async def correlate_new_alert(alert: Alert, session: AsyncSession) -> None:
    """Correlate a newly generated Alert with existing unresolved AlertCorrelations (incidents).
    
    If an existing unresolved correlation matches the alert source/resource within a 10-minute window,
    associate the alert with it and recalculate threat score. Otherwise, create a new correlation.
    """
    try:
        source = alert.source
        
        # Look back 10 minutes for active (unresolved) correlations
        time_limit = datetime.utcnow() - timedelta(minutes=10)
        
        # Query active correlations for the same source
        stmt = (
            select(AlertCorrelation)
            .where(AlertCorrelation.resolved == False)
            .where(AlertCorrelation.timestamp >= time_limit)
        )
        
        # Simple heuristic: extract a target/resource name from title
        # Alert titles look like: "CPU Exhaustion: production-web-01", "API Latency Spike: payment-service"
        target_name = "Unknown"
        if ":" in alert.title:
            target_name = alert.title.split(":")[-1].strip()
            
        result = await session.execute(stmt)
        active_correlations = result.scalars().all()
        
        matched_correlation: Optional[AlertCorrelation] = None
        for corr in active_correlations:
            # If correlation name contains target_name, or they share the same source
            if target_name != "Unknown" and target_name in corr.incident_name:
                matched_correlation = corr
                break
            elif corr.incident_name.endswith(f"in {source.upper()}"):
                matched_correlation = corr
                break
                
        if matched_correlation:
            logger.info(f"Correlating Alert {alert.id} with existing incident {matched_correlation.id}")
            # Append ID
            existing_ids = [aid.strip() for aid in matched_correlation.alert_ids.split(",") if aid.strip()]
            if str(alert.id) not in existing_ids:
                existing_ids.append(str(alert.id))
                matched_correlation.alert_ids = ",".join(existing_ids)
            
            # Recalculate threat score based on alert severities
            # CRITICAL = 65, MEDIUM = 35, LOW = 15
            severity_points = 0
            alert_ids = [int(aid) for aid in existing_ids if aid.isdigit()]
            for aid in alert_ids:
                linked_alert = await session.get(Alert, aid)
                if linked_alert:
                    if linked_alert.severity == "CRITICAL":
                        severity_points += 65
                    elif linked_alert.severity == "MEDIUM":
                        severity_points += 35
                    else:
                        severity_points += 15
            
            # Capped at 100
            matched_correlation.threat_score = min(float(severity_points), 100.0)
            
            # Update description
            matched_correlation.description = (
                f"Correlated security incident containing {len(alert_ids)} alerts "
                f"from {source} targeting {target_name}. Cumulative threat score: {matched_correlation.threat_score:.1f}."
            )
            
            session.add(matched_correlation)
            await session.commit()
            
            # Update alert's correlation ID
            alert.correlated_incident_id = matched_correlation.id
            session.add(alert)
            await session.commit()
        else:
            # Create a new AlertCorrelation
            logger.info(f"No matching active incident. Creating new correlation for Alert {alert.id}")
            
            initial_score = 15.0
            if alert.severity == "CRITICAL":
                initial_score = 65.0
            elif alert.severity == "MEDIUM":
                initial_score = 35.0
                
            incident_name = f"Security Incident in {source.upper()}"
            if target_name != "Unknown":
                incident_name = f"Multiple Events on {target_name} ({source.upper()})"
                
            description = (
                f"Correlated security incident containing 1 alert "
                f"from {source} targeting {target_name}. Threat score: {initial_score:.1f}."
            )
            
            new_correlation = AlertCorrelation(
                incident_name=incident_name,
                threat_score=initial_score,
                description=description,
                alert_ids=str(alert.id),
                timestamp=datetime.utcnow(),
                resolved=False
            )
            session.add(new_correlation)
            await session.commit()
            await session.refresh(new_correlation)
            
            # Update alert
            alert.correlated_incident_id = new_correlation.id
            session.add(alert)
            await session.commit()
            
    except Exception:
        logger.exception("Failed to correlate alerts in engine")
