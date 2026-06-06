from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime


class ApiHealth(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    service_name: str
    url: str
    status_code: int
    response_time_ms: float
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class QueueMetrics(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    queue_name: str
    total_messages: int
    consumers: int
    unacked_messages: int
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ServerHealth(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    host_name: str
    ip_address: str
    cpu_usage_pct: float
    memory_usage_pct: float
    disk_usage_pct: float
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class SystemLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    service_name: str
    log_level: str  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    message: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class Alert(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    source: str  # api_health, queue_metrics, server_health, system_log
    severity: str  # LOW, MEDIUM, CRITICAL
    title: str
    description: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    resolved: bool = Field(default=False)
    correlated_incident_id: Optional[int] = Field(default=None)


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    hashed_password: str
    role: str = Field(default="Viewer")  # Admin, Security Analyst, Viewer


class Anomaly(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    source: str  # api_health, queue_metrics, server_health
    metric_name: str
    metric_value: float
    detection_method: str  # Z-Score, Moving Average, Isolation Forest
    score: float
    description: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class AlertCorrelation(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    incident_name: str
    threat_score: float  # 0 to 100
    description: str
    alert_ids: str  # Comma-separated alert IDs
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    resolved: bool = Field(default=False)

