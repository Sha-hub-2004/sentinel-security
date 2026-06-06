try:
    from pydantic import BaseSettings, Field
except ImportError:
    from pydantic.v1 import BaseSettings, Field
from typing import Optional


class Settings(BaseSettings):
    DATABASE_URL: str = Field("sqlite+aiosqlite:///./dev.db")
    RABBITMQ_URL: str = Field("amqp://guest:guest@localhost/")
    ELASTICSEARCH_URL: str = Field("http://localhost:9200")
    
    # Alert configurations
    SLACK_WEBHOOK_URL: Optional[str] = Field(None)
    TEAMS_WEBHOOK_URL: Optional[str] = Field(None)
    SMTP_HOST: Optional[str] = Field(None)
    SMTP_PORT: int = Field(587)
    SMTP_USER: Optional[str] = Field(None)
    SMTP_PASSWORD: Optional[str] = Field(None)
    ALERT_EMAIL_RECIPIENT: Optional[str] = Field(None)
    ALERT_THROTTLE_WINDOW: int = Field(300)  # in seconds

    # JWT Authentication settings
    JWT_SECRET: str = Field("super-secret-key-for-soc-siem-jwt-tokens-change-in-prod")
    JWT_ALGORITHM: str = Field("HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(60)

    class Config:
        env_file = ".env"


settings = Settings()

