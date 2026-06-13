from fastapi import APIRouter, Depends, HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select
from typing import List, Optional
from app.db.session import get_session
from app.models import Alert, AlertCorrelation, User
from app.schemas import AlertRead, AlertUpdate, AlertCorrelationRead
from app.logger import get_logger
from app.core.security import get_current_user, RoleChecker

router = APIRouter()
logger = get_logger("alerts_api")


@router.get("/", response_model=List[AlertRead])
async def get_alerts(
    resolved: Optional[bool] = None,
    limit: int = 100,
    offset: int = 0,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Retrieve historical and active security alerts."""
    try:
        query = select(Alert)
        if resolved is not None:
            query = query.where(Alert.resolved == resolved)
        # Order by newest first
        query = query.order_by(Alert.timestamp.desc()).offset(offset).limit(limit)
        results = await session.execute(query)
        alerts = results.scalars().all()
        return alerts
    except Exception:
        logger.exception("Failed to retrieve alerts")
        raise HTTPException(status_code=500, detail="Failed to retrieve alerts")


@router.put("/{alert_id}/resolve", response_model=AlertRead)
async def resolve_alert(
    alert_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(RoleChecker(["Security Analyst", "Admin"])),
):
    """Mark an active security alert as resolved."""
    try:
        alert = await session.get(Alert, alert_id)
        if not alert:
            raise HTTPException(status_code=404, detail="Alert not found")
        alert.resolved = True
        session.add(alert)
        await session.commit()
        await session.refresh(alert)
        logger.info(f"Alert {alert_id} marked as resolved.")
        return alert
    except HTTPException:
        raise
    except Exception:
        logger.exception(f"Failed to resolve alert {alert_id}")
        raise HTTPException(status_code=500, detail="Failed to resolve alert")


@router.get("/correlations", response_model=List[AlertCorrelationRead])
async def get_alert_correlations(
    resolved: Optional[bool] = None,
    limit: int = 100,
    offset: int = 0,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Retrieve historical and active alert correlations (security incidents)."""
    try:
        query = select(AlertCorrelation)
        if resolved is not None:
            query = query.where(AlertCorrelation.resolved == resolved)
        # Order by newest first
        query = query.order_by(AlertCorrelation.timestamp.desc()).offset(offset).limit(limit)
        results = await session.execute(query)
        correlations = results.scalars().all()
        return correlations
    except Exception:
        logger.exception("Failed to retrieve alert correlations")
        raise HTTPException(status_code=500, detail="Failed to retrieve alert correlations")


@router.put("/correlations/{correlation_id}/resolve", response_model=AlertCorrelationRead)
async def resolve_alert_correlation(
    correlation_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(RoleChecker(["Security Analyst", "Admin"])),
):
    """Mark a security incident correlation and all its nested alerts as resolved."""
    try:
        correlation = await session.get(AlertCorrelation, correlation_id)
        if not correlation:
            raise HTTPException(status_code=404, detail="Alert correlation not found")
        
        correlation.resolved = True
        session.add(correlation)
        
        # Resolve all linked alerts
        if correlation.alert_ids:
            alert_ids = [int(aid.strip()) for aid in correlation.alert_ids.split(",") if aid.strip()]
            for aid in alert_ids:
                alert = await session.get(Alert, aid)
                if alert:
                    alert.resolved = True
                    session.add(alert)
                    
        await session.commit()
        await session.refresh(correlation)
        logger.info(f"Alert correlation {correlation_id} (and linked alerts) marked as resolved.")
        return correlation
    except HTTPException:
        raise
    except Exception:
        logger.exception(f"Failed to resolve alert correlation {correlation_id}")
        raise HTTPException(status_code=500, detail="Failed to resolve alert correlation")

