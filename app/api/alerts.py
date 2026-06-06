from fastapi import APIRouter, Depends, HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select
from typing import List, Optional
from app.db.session import get_session
from app.models import Alert
from app.schemas import AlertRead, AlertUpdate
from app.logger import get_logger

router = APIRouter()
logger = get_logger("alerts_api")


@router.get("/", response_model=List[AlertRead])
async def get_alerts(
    resolved: Optional[bool] = None,
    limit: int = 100,
    offset: int = 0,
    session: AsyncSession = Depends(get_session),
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
