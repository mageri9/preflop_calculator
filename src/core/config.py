import os
from pydantic import BaseModel

class Settings(BaseModel):
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "123456789:TEST_BOT_TOKEN")
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///poker.db")
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    CORS_ORIGINS: list[str] = ["*"]

settings = Settings()