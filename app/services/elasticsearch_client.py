import asyncio
from typing import Any, Dict, Optional
from datetime import datetime
from elasticsearch import AsyncElasticsearch
from app.core.config import settings
from app.logger import get_logger

logger = get_logger("elasticsearch_client")

_es_client: Optional[AsyncElasticsearch] = None


def get_es_client() -> Optional[AsyncElasticsearch]:
    """Retrieve or initialize the async Elasticsearch client."""
    global _es_client
    if _es_client is None and settings.ELASTICSEARCH_URL:
        try:
            # We initialize the client. It won't throw until a request is made or we ping.
            _es_client = AsyncElasticsearch(
                settings.ELASTICSEARCH_URL,
                request_timeout=5.0,
                max_retries=2,
                retry_on_timeout=True
            )
        except Exception:
            logger.exception("Failed to instantiate Elasticsearch client")
            _es_client = None
    return _es_client


async def close_es() -> None:
    """Close the Elasticsearch connection."""
    global _es_client
    if _es_client is not None:
        try:
            await _es_client.close()
            logger.info("Elasticsearch connection closed.")
        except Exception:
            logger.exception("Error closing Elasticsearch connection")
        finally:
            _es_client = None


def sanitize_document(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Helper to convert datetime values and other non-serializable objects to string format."""
    cleaned = {}
    for k, v in doc.items():
        if isinstance(v, datetime):
            cleaned[k] = v.isoformat()
        else:
            cleaned[k] = v
    return cleaned


async def send_to_elasticsearch(index_prefix: str, document: Dict[str, Any]) -> bool:
    """Index a document to Elasticsearch under a daily index pattern: sentinel-{index_prefix}-YYYY.MM.DD.
    
    If Elasticsearch is offline, this fails gracefully and logs a warning.
    """
    client = get_es_client()
    if client is None:
        return False

    # Sanitize document first
    document = sanitize_document(document)

    # Standardize timestamp field for Elasticsearch/Kibana
    if "@timestamp" not in document:
        ts_str = document.get("timestamp")
        if ts_str:
            document["@timestamp"] = ts_str
        else:
            document["@timestamp"] = datetime.utcnow().isoformat()
            
    # Format daily index name
    today_str = datetime.utcnow().strftime("%Y.%m.%d")
    index_name = f"sentinel-{index_prefix}-{today_str}"

    try:
        await client.index(index=index_name, document=document)
        return True
    except Exception as exc:
        # Gracefully handle connection errors so API operations don't block/fail
        logger.debug(f"Elasticsearch index write failed for {index_name} (using local/SQLite only fallback): {exc}")
        return False
