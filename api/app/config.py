from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    database_url: str = "postgresql+psycopg://crm:crm@db:5432/crm"
    environment: str = "development"
    release: str = "dev"

    secret_key: str = "change-me-in-production-to-a-long-random-value"
    token_ttl_hours: int = 12
    # Created on startup when the users table is empty, so a fresh install can log in.
    admin_email: str = "admin@evolve.test"
    admin_password: str = "admin123"


@lru_cache
def get_settings() -> Settings:
    return Settings()
