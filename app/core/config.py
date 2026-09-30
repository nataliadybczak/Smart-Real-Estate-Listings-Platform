from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """App configuration read from environment variables / the .env file."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "local"
    database_url: str = "mysql+pymysql://app:app@127.0.0.1:3306/real_estate?charset=utf8mb4"
    database_ssl_ca: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
