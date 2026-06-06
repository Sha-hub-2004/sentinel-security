from pydantic import BaseModel, HttpUrl
from datetime import datetime
from typing import Optional, Dict, Any


class ApiHealthCreate(BaseModel):
    service_name: str
    url: HttpUrl
    status_code: int
    response_time_ms: float
    timestamp: Optional[datetime] = None


class ApiHealthRead(ApiHealthCreate):
    id: int


class QueueMetricsCreate(BaseModel):
    queue_name: str
    total_messages: int
    consumers: int
    unacked_messages: int
    timestamp: Optional[datetime] = None


class QueueMetricsRead(QueueMetricsCreate):
    id: int


class PublishRequest(BaseModel):
    routing_key: str
    payload: Dict[str, Any]
    persistent: bool = True


class PublishResponse(BaseModel):
    success: bool
    message: str


class ServerHealthCreate(BaseModel):
    host_name: str
    ip_address: str
    cpu_usage_pct: float
    memory_usage_pct: float
    disk_usage_pct: float
    timestamp: Optional[datetime] = None


class ServerHealthRead(ServerHealthCreate):
    id: int


class SystemLogCreate(BaseModel):
    service_name: str
    log_level: str  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    message: str
    timestamp: Optional[datetime] = None


class SystemLogRead(SystemLogCreate):
    id: int


class AlertRead(BaseModel):
    id: int
    source: str
    severity: str
    title: str
    description: str
    timestamp: datetime
    resolved: bool

    class Config:
        orm_mode = True


class AlertUpdate(BaseModel):
    resolved: Optional[bool] = None


class UserCreate(BaseModel):
    username: str
    password: str
    role: Optional[str] = "Viewer"  # Admin, Security Analyst, Viewer


class UserRead(BaseModel):
    id: int
    username: str
    role: str

    class Config:
        orm_mode = True


class Token(BaseModel):
    access_token: str
    token_type: str
    role: str
    username: str


class TokenData(BaseModel):
    username: Optional[str] = None
    role: Optional[str] = None


class AnomalyCreate(BaseModel):
    source: str
    metric_name: str
    metric_value: float
    detection_method: str
    score: float
    description: str
    timestamp: Optional[datetime] = None


class AnomalyRead(AnomalyCreate):
    id: int

    class Config:
        orm_mode = True


class AlertCorrelationRead(BaseModel):
    id: int
    incident_name: str
    threat_score: float
    description: str
    alert_ids: str
    timestamp: datetime
    resolved: bool

    class Config:
        orm_mode = True

