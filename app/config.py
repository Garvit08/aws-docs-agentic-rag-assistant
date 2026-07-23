from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables and .env."""

    aws_region: str = "ap-southeast-2"
    aws_profile: str | None = None
    bedrock_model_id: str = "au.anthropic.claude-sonnet-4-5-20250929-v1:0"

    llm_provider: Literal["bedrock", "fake"] = "fake"
    embeddings_provider: Literal["bedrock", "fake"] = "fake"
    persistence: Literal["memory", "dynamodb"] = "memory"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return a process-wide cached Settings instance.

    Cached so settings load once; tests can clear the cache or override the
    dependency to inject their own configuration.
    """
    return Settings()
