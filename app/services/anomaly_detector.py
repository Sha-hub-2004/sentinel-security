import numpy as np
import pandas as pd
from typing import Optional, Dict, Any, List, Tuple
from sklearn.ensemble import IsolationForest
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from app.models import ApiHealth, QueueMetrics, ServerHealth, Anomaly
from app.logger import get_logger
from datetime import datetime

logger = get_logger("anomaly_detector")

# Minimum number of historical data points required to run Isolation Forest/Z-Score reasonably
MIN_DATA_POINTS = 10


async def fetch_historical_metrics(
    session: AsyncSession, source: str, resource_name: str, metric_name: str, limit: int = 100
) -> List[float]:
    """Fetch recent historical values for a specific resource and metric."""
    try:
        if source == "api_health":
            stmt = (
                select(ApiHealth.response_time_ms)
                .where(ApiHealth.service_name == resource_name)
                .order_by(ApiHealth.timestamp.desc())
                .limit(limit)
            )
        elif source == "queue_metrics":
            if metric_name == "total_messages":
                stmt = (
                    select(QueueMetrics.total_messages)
                    .where(QueueMetrics.queue_name == resource_name)
                    .order_by(QueueMetrics.timestamp.desc())
                    .limit(limit)
                )
            else:
                stmt = (
                    select(QueueMetrics.unacked_messages)
                    .where(QueueMetrics.queue_name == resource_name)
                    .order_by(QueueMetrics.timestamp.desc())
                    .limit(limit)
                )
        elif source == "server_health":
            if metric_name == "cpu_usage_pct":
                stmt = (
                    select(ServerHealth.cpu_usage_pct)
                    .where(ServerHealth.host_name == resource_name)
                    .order_by(ServerHealth.timestamp.desc())
                    .limit(limit)
                )
            elif metric_name == "memory_usage_pct":
                stmt = (
                    select(ServerHealth.memory_usage_pct)
                    .where(ServerHealth.host_name == resource_name)
                    .order_by(ServerHealth.timestamp.desc())
                    .limit(limit)
                )
            else:
                stmt = (
                    select(ServerHealth.disk_usage_pct)
                    .where(ServerHealth.host_name == resource_name)
                    .order_by(ServerHealth.timestamp.desc())
                    .limit(limit)
                )
        else:
            return []

        result = await session.execute(stmt)
        # Convert to list and reverse so it is chronological (oldest to newest)
        values = [float(v) for v in result.scalars().all()]
        values.reverse()
        return values
    except Exception:
        logger.exception(f"Error fetching historical metrics for {source} - {resource_name}")
        return []


def detect_zscore_anomaly(current_val: float, history: List[float], threshold: float = 3.0) -> Tuple[bool, float]:
    """Z-Score anomaly detection: (value - mean) / std."""
    if len(history) < MIN_DATA_POINTS:
        return False, 0.0
    arr = np.array(history)
    mean = np.mean(arr)
    std = np.std(arr)
    if std == 0:
        return False, 0.0
    
    z_score = (current_val - mean) / std
    is_anomaly = abs(z_score) > threshold
    return bool(is_anomaly), float(z_score)


def detect_moving_average_anomaly(
    current_val: float, history: List[float], window: int = 10, threshold_multiplier: float = 2.5
) -> Tuple[bool, float]:
    """Moving Average anomaly detection using rolling standard deviations."""
    if len(history) < MIN_DATA_POINTS:
        return False, 0.0
    
    # Use the tail of history for the rolling window
    sub_hist = history[-window:]
    mean = np.mean(sub_hist)
    std = np.std(sub_hist)
    if std == 0:
        return False, 0.0
        
    diff = abs(current_val - mean)
    is_anomaly = diff > (threshold_multiplier * std)
    deviation = diff / std if std > 0 else 0.0
    return bool(is_anomaly), float(deviation)


def detect_isolation_forest_anomaly(current_val: float, history: List[float], contamination: float = 0.1) -> Tuple[bool, float]:
    """Isolation Forest anomaly detection."""
    if len(history) < MIN_DATA_POINTS:
        return False, 0.0
        
    # Prepare training data
    arr = np.array(history).reshape(-1, 1)
    
    # Train Isolation Forest
    clf = IsolationForest(contamination=contamination, random_state=42, n_estimators=50)
    clf.fit(arr)
    
    # Score the current value (-1 for anomaly, 1 for normal)
    pred = clf.predict([[current_val]])[0]
    
    # Decision function returns the anomaly score (lower means more anomalous, i.e., negative values are anomalies)
    score = clf.decision_function([[current_val]])[0]
    
    is_anomaly = pred == -1
    # Standardize score output: map decision function to a value where higher is more anomalous
    anomaly_score = float(-score)
    return bool(is_anomaly), anomaly_score


async def evaluate_anomalies(
    session: AsyncSession, source: str, resource_name: str, data: Dict[str, Any]
) -> List[Anomaly]:
    """Evaluate all metrics in an incoming payload and save detected anomalies."""
    detected_anomalies = []
    
    # Map metrics to inspect based on source
    metrics_to_check = []
    if source == "api_health":
        metrics_to_check = [("response_time_ms", float(data.get("response_time_ms", 0.0)))]
    elif source == "queue_metrics":
        metrics_to_check = [
            ("total_messages", float(data.get("total_messages", 0.0))),
            ("unacked_messages", float(data.get("unacked_messages", 0.0))),
        ]
    elif source == "server_health":
        metrics_to_check = [
            ("cpu_usage_pct", float(data.get("cpu_usage_pct", 0.0))),
            ("memory_usage_pct", float(data.get("memory_usage_pct", 0.0))),
            ("disk_usage_pct", float(data.get("disk_usage_pct", 0.0))),
        ]

    for metric_name, current_val in metrics_to_check:
        history = await fetch_historical_metrics(session, source, resource_name, metric_name)
        if len(history) < MIN_DATA_POINTS:
            continue

        # 1. Z-Score detection (Trigger alert if extremely deviant)
        z_anomaly, z_score = detect_zscore_anomaly(current_val, history)
        if z_anomaly:
            desc = f"Z-Score anomaly detected on {resource_name} {metric_name}: value {current_val} deviated by {z_score:.2f} standard deviations."
            anomaly_obj = Anomaly(
                source=source,
                metric_name=metric_name,
                metric_value=current_val,
                detection_method="Z-Score",
                score=z_score,
                description=desc,
                timestamp=datetime.utcnow()
            )
            session.add(anomaly_obj)
            detected_anomalies.append(anomaly_obj)
            logger.warning(desc)
            
            try:
                from app.core.metrics import ANOMALIES_DETECTED_TOTAL
                ANOMALIES_DETECTED_TOTAL.labels(source=source, detection_method="Z-Score").inc()
            except Exception:
                pass

        # 2. Isolation Forest detection (Multivariate anomaly detection helper)
        ifforest_anomaly, if_score = detect_isolation_forest_anomaly(current_val, history)
        if ifforest_anomaly:
            desc = f"Isolation Forest flagged anomaly on {resource_name} {metric_name}: value {current_val} had anomaly score {if_score:.3f}."
            anomaly_obj = Anomaly(
                source=source,
                metric_name=metric_name,
                metric_value=current_val,
                detection_method="Isolation Forest",
                score=if_score,
                description=desc,
                timestamp=datetime.utcnow()
            )
            session.add(anomaly_obj)
            detected_anomalies.append(anomaly_obj)
            logger.warning(desc)

            try:
                from app.core.metrics import ANOMALIES_DETECTED_TOTAL
                ANOMALIES_DETECTED_TOTAL.labels(source=source, detection_method="Isolation Forest").inc()
            except Exception:
                pass

        # 3. Moving Average detection (Detect sudden volatility shifts)
        ma_anomaly, ma_score = detect_moving_average_anomaly(current_val, history)
        if ma_anomaly:
            desc = f"Moving Average anomaly on {resource_name} {metric_name}: value {current_val} exceeded rolling mean by {ma_score:.2f} dev-factors."
            anomaly_obj = Anomaly(
                source=source,
                metric_name=metric_name,
                metric_value=current_val,
                detection_method="Moving Average",
                score=ma_score,
                description=desc,
                timestamp=datetime.utcnow()
            )
            session.add(anomaly_obj)
            detected_anomalies.append(anomaly_obj)
            logger.warning(desc)

            try:
                from app.core.metrics import ANOMALIES_DETECTED_TOTAL
                ANOMALIES_DETECTED_TOTAL.labels(source=source, detection_method="Moving Average").inc()
            except Exception:
                pass
            
    if detected_anomalies:
        await session.commit()
        try:
            import asyncio
            from app.services.elasticsearch_client import send_to_elasticsearch
            for anomaly in detected_anomalies:
                asyncio.create_task(send_to_elasticsearch("anomalies", anomaly.dict()))
        except Exception:
            pass
        
    return detected_anomalies
