from typing import Any, Dict, Optional
import json
import asyncio
from aio_pika import connect_robust, RobustConnection, RobustChannel, ExchangeType, Message
from aio_pika.abc import AbstractRobustExchange
from app.logger import get_logger
from app.core.config import settings

logger = get_logger("rabbitmq")

# Module-level connection/channel/exchange handles
_connection: Optional[RobustConnection] = None
_channel: Optional[RobustChannel] = None
_exchange: Optional[AbstractRobustExchange] = None


async def init_rabbit() -> None:
    """Establish a robust connection and exchange to RabbitMQ.

    This should be non-fatal for the API: when RabbitMQ is down we keep
    the module globals set to None so publish_message() uses the local
    fallback.
    """
    global _connection, _channel, _exchange

    # Ensure we start from a clean state
    _connection = None
    _channel = None
    _exchange = None

    try:
        _connection = await connect_robust(settings.RABBITMQ_URL)
        _channel = await _connection.channel(publisher_confirms=True)
        _exchange = await _channel.declare_exchange("monitoring", ExchangeType.TOPIC, durable=True)
        logger.info("Connected to RabbitMQ and declared exchange 'monitoring'")
    except Exception:
        # RabbitMQ is optional for dev; fall back to local processing.
        _connection = None
        _channel = None
        _exchange = None
        logger.exception("Failed to initialize RabbitMQ connection (RabbitMQ is optional; using local fallback)" )


async def close_rabbit() -> None:
    """Close the channel and connection cleanly."""
    global _connection, _channel
    try:
        if _channel:
            await _channel.close()
        if _connection:
            await _connection.close()
        logger.info("RabbitMQ connection closed")
    except Exception:
        logger.exception("Error closing RabbitMQ connection")


async def publish_message(routing_key: str, payload: Dict[str, Any]) -> bool:
    """Publish a JSON message to the `monitoring` exchange with given routing key.

    If RabbitMQ is unavailable, it gracefully falls back to direct local processing.
    """
    global _exchange
    if _exchange is None:
        logger.warning(f"RabbitMQ exchange offline. Routing telemetry '{routing_key}' to local Alert Engine fallback.")
        try:
            from app.db.session import async_session
            from app.services.alerts import evaluate_metric
            
            source = routing_key
            if "." in routing_key:
                source = routing_key.split(".")[-1]
                
            async with async_session() as session:
                await evaluate_metric(source, payload, session)
            return True
        except Exception:
            logger.exception("Failed to process metric via local Alert Engine fallback")
            return False

    try:
        body = json.dumps(payload, default=str).encode("utf-8")
        message = Message(body=body)
        await _exchange.publish(message, routing_key=routing_key)
    except Exception:
        logger.exception("Failed to publish message to RabbitMQ")
        return False

    logger.info("Published message to RabbitMQ: %s", routing_key)
    return True


