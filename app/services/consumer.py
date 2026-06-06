import asyncio
import json
from typing import Any, Dict
from aio_pika import connect_robust, ExchangeType, IncomingMessage
from app.logger import get_logger
from app.core.config import settings
from app.db.session import async_session
from app.services.alerts import evaluate_metric

logger = get_logger("consumer")


async def on_message(message: IncomingMessage) -> None:
    """Callback triggered whenever a message is received from RabbitMQ."""
    async with message.process():
        try:
            routing_key = message.routing_key or "unknown"
            body = message.body.decode("utf-8")
            data: Dict[str, Any] = json.loads(body)
            logger.info(f"Received message from broker on topic: '{routing_key}'")

            # Extract source from routing key (e.g., "api_health", "queue_metrics")
            # Usually published as direct names or "monitoring.api_health"
            source = routing_key
            if "." in routing_key:
                source = routing_key.split(".")[-1]

            # Standardized sources
            valid_sources = ["api_health", "queue_metrics", "server_health", "system_log"]
            if source not in valid_sources:
                logger.warning(f"Unrecognized metric source: '{source}'. Skipping evaluation.")
                return

            # Open a new database session to evaluate and save potential alerts
            async with async_session() as session:
                await evaluate_metric(source, data, session)

        except json.JSONDecodeError:
            logger.error(f"Received malformed JSON message: {message.body}")
        except Exception:
            logger.exception("Error processing consumer message")


async def start_consumer() -> None:
    """Establishes robust connection to RabbitMQ, binds queues, and begins consuming."""
    logger.info("Initializing RabbitMQ Background Consumer...")
    
    # Retry loop to handle startup delays of RabbitMQ broker
    retries = 5
    connection = None
    
    for i in range(retries):
        try:
            connection = await connect_robust(settings.RABBITMQ_URL)
            logger.info("Successfully connected to RabbitMQ broker.")
            break
        except Exception as exc:
            if i == retries - 1:
                logger.error("Could not connect to RabbitMQ broker after maximum retries.")
                raise exc
            logger.warning(f"RabbitMQ connection failed (attempt {i+1}/{retries}). Retrying in 5 seconds...")
            await asyncio.sleep(5)

    if connection is None:
        return

    try:
        channel = await connection.channel()
        # Ensure we declare exchange in case consumer starts before publisher
        exchange = await channel.declare_exchange(
            "monitoring", 
            ExchangeType.TOPIC, 
            durable=True
        )

        # Declare a persistent, dedicated queue for the Alert Processor
        queue = await channel.declare_queue("alerts_processor", durable=True)

        # Bind the queue to the exchange for all routing keys (wildcard matching '#')
        # This listens to both direct keys like "api_health" and dot-separated hierarchies like "monitoring.#"
        await queue.bind(exchange, routing_key="#")
        await queue.bind(exchange, routing_key="api_health")
        await queue.bind(exchange, routing_key="queue_metrics")
        await queue.bind(exchange, routing_key="server_health")
        await queue.bind(exchange, routing_key="system_log")

        logger.info("Consumer queue 'alerts_processor' is successfully bound. Listening for metrics...")

        # Begin consumption loop
        await queue.consume(on_message)

        # Keep the consumer running forever by sleeping
        while True:
            await asyncio.sleep(3600)

    except asyncio.CancelledError:
        logger.info("Consumer loop cancelled, shutting down cleanly...")
    except Exception:
        logger.exception("Fatal error in consumer event loop")
    finally:
        if connection and not connection.is_closed:
            await connection.close()
            logger.info("RabbitMQ consumer connection closed.")
