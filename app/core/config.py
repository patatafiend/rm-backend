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
    AWS_REGION: str = "ap-southeast-1"
    AWS_ACCESS_KEY_ID: str
    AWS_SECRET_ACCESS_KEY: str
    S3_BUCKET_NAME: str
    S3_PRESIGNED_URL_EXPIRY: int = 300

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