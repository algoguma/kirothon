from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    api_id: int = 0
    api_hash: str = ""
    encryption_key: str = ""

    llm_base_url: str = ""
    llm_model: str = ""
    llm_timeout_sec: float = 30
    llm_use_stub: bool = True

    database_url: str = "sqlite+aiosqlite:///./kirothon.db"


@lru_cache
def get_settings() -> Settings:
    return Settings()
