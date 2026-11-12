from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    database_url: str = "postgresql+psycopg://crm:crm@db:5432/crm"
    environment: str = "development"
    release: str = "dev"


@lru_cache
def get_settings() -> Settings:
    return Settings()
