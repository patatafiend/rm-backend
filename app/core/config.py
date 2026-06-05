from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    ENV: str | None = "DEV"
    APP_NAME: str = "RM API"
    API_V1_STR: str = "/api/v1"

    FRONTEND_URL: str
    DATABASE_URL: str

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ALGORITHM: str = "HS256"
    JWT_SECRET_KEY: str
    JWT_REFRESH_SECRET_KEY: str
    JWT_PASSWORD_RESET_SECRET_KEY: str
    JWT_MFA_SECRET_KEY: str

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
        "extra": "ignore"
    }


@lru_cache()
def get_settings():
    return Settings()


settings = get_settings()