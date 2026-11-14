from functools import lru_cache

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Run from backend/: the repo-root .env is read first, backend/.env overrides it.
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    # Telegram api_id/api_hash are entered per user at login (spec 3.2), not configured here.
    encryption_key: str = ""

    # VLLM_* are the prototype's names for the same values (repo-root .env).
    llm_base_url: str = Field(
        default="", validation_alias=AliasChoices("LLM_BASE_URL", "VLLM_BASE_URL")
    )
    llm_model: str = Field(default="", validation_alias=AliasChoices("LLM_MODEL", "VLLM_MODEL"))
    llm_timeout_sec: float = 30
    llm_use_stub: bool = True

    database_url: str = "sqlite+aiosqlite:///./kirothon.db"

    @field_validator("llm_base_url")
    @classmethod
    def strip_v1(cls, value: str) -> str:
        # The AI module appends /v1; VLLM_BASE_URL already includes it.
        value = value.strip().rstrip("/")
        return value.removesuffix("/v1")


@lru_cache
def get_settings() -> Settings:
    return Settings()
