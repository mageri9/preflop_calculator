from pydantic import BaseModel


class Settings(BaseModel):
    BOT_TOKEN: str = "123456789:TEST_BOT_TOKEN"
    ENVIRONMENT: str = "development"
    DATABASE_URL: str = "sqlite:///poker.db"
    REDIS_URL: str = "redis://localhost:6379/0"
    CORS_ORIGINS: list[str] = ["*"]


settings = Settings()
