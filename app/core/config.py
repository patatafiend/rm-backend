from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    ENV: str | None = "DEV"
    FRONTEND_URL: str
    DATABASE_URL: str

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


setting = get_settings()
