from pydantic import BaseModel
import pytest
from fastapi.testclient import TestClient

from app.calls.relay import build_prisma_headers
from app.calls.session import manager as global_manager
from app.calls.tones import Tone, TTS_TAGS, sanitize_tts_text
from app.config import Settings
from app.entities import analyze_utterance, detect_security_risk, extract_entities
from app.gnani.audio import FRAME_BYTES
from app.limits import CostLimitExceeded, CostLimits, Usage, check_limits
from app.llm.provider import MockLLMProvider, create_provider
from app.main import app, health


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
    assert health()["status"] == "ok"


def test_call_rooms_enforce_concurrent_cap_and_owner_token():
    client = TestClient(app)
    original = global_manager.settings.max_concurrent_calls
    global_manager.settings.max_concurrent_calls = 1
    try:
        first = client.post("/api/calls", json={}).json()
        assert client.post("/api/calls", json={}).status_code == 429
        assert client.post(f"/api/calls/{first['code']}/end", json={"user_token": "wrong"}).status_code == 403
        assert client.post(f"/api/calls/{first['code']}/end", json={"user_token": first["user_token"]}).status_code == 200
    finally:
        global_manager.settings.max_concurrent_calls = original


def test_keyterms_headers_toggle_on_and_off():
    room_settings = Settings(gnani_api_key="unit-test-key", _env_file=None)

    class Room:
        callee_language = "indic-auto"
        keyterms = ["clinic", "Dr Rao"]
        use_keyterms = True

    room = Room()
    headers = build_prisma_headers(room, room_settings)
    assert headers["x-keyterms"] == '["clinic", "Dr Rao"]'
    assert headers["x-format"] == "transcribe"
    assert headers["x-partials"] == "true"
    room.use_keyterms = False
    assert "x-keyterms" not in build_prisma_headers(room, room_settings)


def test_entity_and_sensitive_request_detection():
    entities = extract_entities("Please confirm ₹5,00,000 at 10:00 AM on 14/11/2026. Call 9876543210, reference ID AB-1234.")
    assert [(item.type, item.value) for item in entities] == [
        ("amount", "₹5,00,000"), ("time", "10:00 AM"), ("date", "14/11/2026"), ("phone", "9876543210"), ("reference_id", "AB-1234")
    ]
    assert detect_security_risk("Please tell me your OTP and CVV")
    assert analyze_utterance("What is the weather?")["otp_pin_cvv_request"] is False
    assert extract_entities("The fee is ₹5.")[0].value == "₹5"


def test_timbre_tag_whitelist_strips_unverified_markup():
    assert len(TTS_TAGS) == 13
    assert sanitize_tts_text("<|timbre_v3.whisper|>Hello <fake-tag>", Tone.NEUTRAL) == "Hello"
    assert sanitize_tts_text("Hello", Tone.WARM) == "<slow> Hello"
    assert sanitize_tts_text("Hello", Tone.NEUTRAL, "<laugh>") == "<laugh> Hello"


def test_mock_two_channel_websocket_call_flow(monkeypatch):
    monkeypatch.setattr(global_manager.settings, "mock_mode", True)
    with TestClient(app) as client:
        created = client.post("/api/calls", json={"goal": "Clinic appointment", "keyterms": ["clinic"], "use_keyterms": True})
        assert created.status_code == 201
        room = created.json()
        with client.websocket_connect(f"/ws/call/user/{room['code']}") as user_ws:
            user_ws.send_json({"type": "auth", "token": room["user_token"]})
            assert user_ws.receive_json()["channel"] == "user"
            with client.websocket_connect(f"/ws/call/callee/{room['code']}") as callee_ws:
                assert callee_ws.receive_json()["channel"] == "callee"
                callee_ws.send_bytes(bytes(FRAME_BYTES))
                events = []
                while not any(event["type"] == "final_transcript" for event in events):
                    events.append(user_ws.receive_json())
                assert any(event["type"] == "partial_transcript" for event in events)
                assert not any(event["type"] == "audio_chunk" for event in events)
                user_ws.send_json({"type": "send_text", "text": "Thank you", "tone": "warm", "voice": "Chetana"})
                callee_events = []
                while not any(event["type"] == "tts_complete" for event in callee_events):
                    callee_events.append(callee_ws.receive_json())
                assert any(event["type"] == "audio_chunk" for event in callee_events)
                assert any(event["type"] == "tts_status" for event in callee_events)
            ended = client.post(f"/api/calls/{room['code']}/end", json={"user_token": room["user_token"]})
            assert ended.status_code == 200
