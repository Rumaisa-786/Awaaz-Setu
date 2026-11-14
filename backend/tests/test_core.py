from pydantic import BaseModel
import pytest

from app.config import Settings
from app.limits import CostLimitExceeded, CostLimits, Usage, check_limits
from app.llm.provider import MockLLMProvider, create_provider


class Reply(BaseModel):
    text: str
    needs_free_text: bool


def test_config_defaults_and_env_parsing(monkeypatch):
    monkeypatch.setenv("MOCK_MODE", "false")
    monkeypatch.setenv("LLM_MODEL", "test-model")
    settings = Settings(_env_file=None)
    assert settings.mock_mode is False
    assert settings.llm_provider == "gemini"
    assert settings.llm_model == "test-model"
    assert settings.daily_cost_limit_usd > 0


def test_cost_guard_blocks_at_cap():
    limits = CostLimits(2, 1, 10, 5, 30, 15)
    check_limits(Usage(daily_usd=1.9, session_requests=4), limits)
    with pytest.raises(CostLimitExceeded, match="session requests"):
        check_limits(Usage(session_requests=5), limits)


def test_mock_llm_returns_valid_json_model():
    value = MockLLMProvider.parse_json('{"text":"Mock response","needs_free_text":false}', Reply)
    assert isinstance(value, Reply)
    assert value.model_dump() == {"text": "Mock response", "needs_free_text": False}


def test_mock_mode_selects_mock_provider():
    assert isinstance(create_provider(Settings(mock_mode=True, _env_file=None)), MockLLMProvider)


def test_health_endpoint():
    from app.main import health
    response = health()
    assert response["status"] == "ok"
