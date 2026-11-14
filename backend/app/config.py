from functools import lru_cache
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False)

    gnani_api_key: SecretStr = SecretStr("")
    gnani_base_url: str = "https://api.vachana.ai"
    llm_provider: str = "gemini"
    llm_model: str = "gemini-3.5-flash-lite"
    gemini_api_key: SecretStr = SecretStr("")
    mock_mode: bool = True
    daily_cost_limit_usd: float = Field(default=5.0, ge=0)
    session_cost_limit_usd: float = Field(default=1.0, ge=0)
    daily_request_limit: int = Field(default=500, ge=0)
    session_request_limit: int = Field(default=100, ge=0)
    daily_audio_minutes_limit: float = Field(default=120.0, ge=0)
    session_duration_minutes_limit: float = Field(default=15.0, gt=0)
    max_concurrent_calls: int = Field(default=10, ge=1)
    call_max_minutes: float = Field(default=15.0, gt=0)
    tts_daily_char_limit: int = Field(default=50_000, ge=1)
    tts_session_char_limit: int = Field(default=5_000, ge=1)
    prisma_reconnect_seconds: float = Field(default=1.0, ge=0.1, le=30)


@lru_cache
def get_settings() -> Settings:
    return Settings()
