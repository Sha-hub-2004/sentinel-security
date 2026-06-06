from fastapi import APIRouter, BackgroundTasks, HTTPException
from app.schemas import PublishRequest, PublishResponse
from app.services.rabbitmq import publish_message
from app.logger import get_logger
import asyncio

router = APIRouter()
logger = get_logger("publish")


@router.post("/", response_model=PublishResponse)
async def publish_message_endpoint(req: PublishRequest, background_tasks: BackgroundTasks):
    """Public endpoint to publish arbitrary JSON payloads to the monitoring exchange.

    Note: This endpoint queues an async publish and returns immediately.
    """
    try:
        # Fire-and-forget scheduling.
        try:
            asyncio.create_task(publish_message(req.routing_key, req.payload))
        except RuntimeError:
            logger.debug("Could not schedule async publish (no running loop)")
        return PublishResponse(success=True, message="Queued for publish")
    except Exception:
        logger.exception("Failed to schedule publish")
        raise HTTPException(status_code=500, detail="publish failed")
