from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "local"
    database_url: str = "mysql+pymysql://app:app@127.0.0.1:3306/real_estate?charset=utf8mb4"


@lru_cache
def get_settings() -> Settings:
    return Settings()
