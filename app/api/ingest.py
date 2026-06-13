from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from app.schemas import (
    ApiHealthCreate,
    ApiHealthRead,
    QueueMetricsCreate,
    QueueMetricsRead,
    ServerHealthCreate,
    ServerHealthRead,
    SystemLogCreate,
    SystemLogRead,
)
from app.db.session import get_session
from sqlmodel.ext.asyncio.session import AsyncSession
from app.models import ApiHealth, QueueMetrics, ServerHealth, SystemLog, User
from app.logger import get_logger
from app.services.rabbitmq import publish_message
from app.services.elasticsearch_client import send_to_elasticsearch
from app.core.security import RoleChecker
from app.core.metrics import INGEST_REQUESTS_TOTAL
import asyncio
from datetime import datetime

router = APIRouter()
logger = get_logger("ingest")


@router.post("/api_health", response_model=ApiHealthRead)
async def ingest_api_health(
    payload: ApiHealthCreate,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(RoleChecker(["Admin"])),
):
    try:
        obj = ApiHealth(
            service_name=payload.service_name,
            url=str(payload.url),
            status_code=payload.status_code,
            response_time_ms=payload.response_time_ms,
            timestamp=payload.timestamp or datetime.utcnow(),
        )
        session.add(obj)
        await session.commit()
        await session.refresh(obj)

        # Fire-and-forget to the message bus (async publish).
        # Avoid using BackgroundTasks+asyncio.create_task (it runs in a worker thread => no running event loop).
        try:
            asyncio.create_task(publish_message("api_health", obj.dict()))
            asyncio.create_task(send_to_elasticsearch("metrics", {"type": "api_health", **obj.dict()}))
        except RuntimeError:
            # Fallback: publish will run on request loop if available; otherwise ignore.
            logger.debug("Could not schedule async publish (no running loop)")

        INGEST_REQUESTS_TOTAL.labels(endpoint="api_health", status="success").inc()
        return obj
    except Exception as exc:
        INGEST_REQUESTS_TOTAL.labels(endpoint="api_health", status="error").inc()
        logger.exception("Failed to ingest api health")
        raise HTTPException(status_code=500, detail="ingest failed") from exc


@router.post("/queue_metrics", response_model=QueueMetricsRead)
async def ingest_queue_metrics(
    payload: QueueMetricsCreate,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(RoleChecker(["Admin"])),
):
    try:
        obj = QueueMetrics(
            queue_name=payload.queue_name,
            total_messages=payload.total_messages,
            consumers=payload.consumers,
            unacked_messages=payload.unacked_messages,
            timestamp=payload.timestamp or datetime.utcnow(),
        )
        session.add(obj)
        await session.commit()
        await session.refresh(obj)

        try:
            asyncio.create_task(publish_message("queue_metrics", obj.dict()))
            asyncio.create_task(send_to_elasticsearch("metrics", {"type": "queue_metrics", **obj.dict()}))
        except RuntimeError:
            logger.debug("Could not schedule async publish (no running loop)")

        INGEST_REQUESTS_TOTAL.labels(endpoint="queue_metrics", status="success").inc()
        return obj
    except Exception:
        INGEST_REQUESTS_TOTAL.labels(endpoint="queue_metrics", status="error").inc()
        logger.exception("Failed to ingest queue metrics")
        raise HTTPException(status_code=500, detail="ingest failed")


@router.post("/server_health", response_model=ServerHealthRead)
async def ingest_server_health(
    payload: ServerHealthCreate,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(RoleChecker(["Admin"])),
):
    try:
        obj = ServerHealth(
            host_name=payload.host_name,
            ip_address=payload.ip_address,
            cpu_usage_pct=payload.cpu_usage_pct,
            memory_usage_pct=payload.memory_usage_pct,
            disk_usage_pct=payload.disk_usage_pct,
            timestamp=payload.timestamp or datetime.utcnow(),
        )
        session.add(obj)
        await session.commit()
        await session.refresh(obj)

        try:
            asyncio.create_task(publish_message("server_health", obj.dict()))
            asyncio.create_task(send_to_elasticsearch("metrics", {"type": "server_health", **obj.dict()}))
        except RuntimeError:
            logger.debug("Could not schedule async publish (no running loop)")

        INGEST_REQUESTS_TOTAL.labels(endpoint="server_health", status="success").inc()
        return obj
    except Exception:
        INGEST_REQUESTS_TOTAL.labels(endpoint="server_health", status="error").inc()
        logger.exception("Failed to ingest server health")
        raise HTTPException(status_code=500, detail="ingest failed")


@router.post("/system_log", response_model=SystemLogRead)
async def ingest_system_log(
    payload: SystemLogCreate,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(RoleChecker(["Admin"])),
):
    try:
        obj = SystemLog(
            service_name=payload.service_name,
            log_level=payload.log_level.upper(),
            message=payload.message,
            timestamp=payload.timestamp or datetime.utcnow(),
        )
        session.add(obj)
        await session.commit()
        await session.refresh(obj)

        try:
            asyncio.create_task(publish_message("system_log", obj.dict()))
            asyncio.create_task(send_to_elasticsearch("logs", obj.dict()))
        except RuntimeError:
            logger.debug("Could not schedule async publish (no running loop)")

        INGEST_REQUESTS_TOTAL.labels(endpoint="system_log", status="success").inc()
        return obj
    except Exception:
        INGEST_REQUESTS_TOTAL.labels(endpoint="system_log", status="error").inc()
        logger.exception("Failed to ingest system log")
        raise HTTPException(status_code=500, detail="ingest failed")

