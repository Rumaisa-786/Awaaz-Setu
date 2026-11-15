import asyncio
import json
from types import SimpleNamespace

import pytest

from scripts import evaluate
from scripts.evaluate import _degrade_to_8k, _metric_rows, _mock_carrier_audio, _wav_bytes, wer_cer
from app.gnani.tts import TTSService, _TTSStreamError, _strip_repeated_wav_header


def test_wer_cer_exact_and_error_rates():
    assert wer_cer("Awaaz Setu 450", "Awaaz Setu 450") == (0.0, 0.0)
    wer, cer = wer_cer("Awaaz Setu", "Awaaz Setoo")
    assert wer == 0.5
    assert 0 < cer < 1


def test_evaluation_pipeline_creates_8khz_degraded_mono_wave():
    clean = _mock_carrier_audio()
    degraded = _degrade_to_8k(clean)
    wav = _wav_bytes(degraded, 8000)
    assert len(degraded) == len(clean) // 2
    assert wav[:4] == b"RIFF"


def test_entity_and_risk_metrics_use_hand_labelled_fixtures():
    result = _metric_rows()
    assert result["entity"]["cases"] == 15
    assert result["entity"]["tp"] == 9
    assert result["risk"]["tp"] == 5


def test_timbre_sse_repeated_wav_headers_are_removed_after_first_chunk():
    header = b"RIFF" + b"\x00" * 4 + b"WAVE" + b"fmt " + b"\x00" * 28
    first, second = header + b"first", header + b"second"
    assert _strip_repeated_wav_header(first, True) == first
    assert _strip_repeated_wav_header(second, False) == b"second"


def test_prisma_vad_silence_and_final_after_speech_end(monkeypatch):
    sent = []
    class Socket:
        async def recv(self): raise AssertionError("Prisma stream must send audio without waiting for a greeting")
        async def send(self, data): sent.append(data)
        def __aiter__(self):
            return self
        async def __anext__(self):
            if not hasattr(self, "events"):
                self.events = iter([
                    json.dumps({"type": "speech_end"}),
                    json.dumps({"type": "transcript", "text": "नमस्ते", "latency": 42}),
                ])
            try: return next(self.events)
            except StopIteration: raise StopAsyncIteration
    class Connect:
        def __init__(self, *args, **kwargs): self.kwargs = kwargs
        async def __aenter__(self):
            monkeypatch.setitem(captured, "headers", self.kwargs["additional_headers"])
            return socket
        async def __aexit__(self, *args): pass
    socket = Socket()
    captured = {}
    monkeypatch.setattr(evaluate.websockets, "connect", Connect)
    settings = SimpleNamespace(gnani_base_url="https://example.invalid", gnani_api_key=SimpleNamespace(get_secret_value=lambda: "test"))
    text, _handshake, latency, _wall = asyncio.run(evaluate._stt_ws(settings, [0] * 512, 16000, "hi-IN", ("डॉक्टर",)))
    assert text == "नमस्ते" and latency == 42
    assert captured["headers"]["x-model"] == "prisma-v3.0"
    assert captured["headers"]["x-keyterms"] == '["\\u0921\\u0949\\u0915\\u094d\\u091f\\u0930"]'
    assert len(sent) == 17
    assert all(len(frame) == 1024 for frame in sent)


def test_tts_tries_streaming_sse_before_websocket(monkeypatch):
    calls = []
    class Manager:
        settings = SimpleNamespace(mock_mode=False, gnani_api_key=SimpleNamespace(get_secret_value=lambda: "test"))
        async def reserve_tts(self, room, count): pass
    class Transport:
        async def send_event(self, payload): pass
        async def send_audio(self, payload): pass
    service = TTSService(Manager(), Manager.settings)
    async def sse(key, payload, transport):
        calls.append(("sse", payload["audio_config"]))
    async def websocket(key, payload, transport):
        calls.append(("websocket", payload["audio_config"]))
    monkeypatch.setattr(service, "_sse", sse)
    monkeypatch.setattr(service, "_websocket", websocket)
    room = SimpleNamespace()
    asyncio.run(service.speak(room, Transport(), "Hello", "female", "hi-IN", "neutral"))
    assert calls == [("sse", {"sample_rate": 24000, "encoding": "linear_pcm", "container": "wav"})]


def test_tts_does_not_restart_websocket_after_partial_sse_audio(monkeypatch):
    calls = []
    class Manager:
        settings = SimpleNamespace(mock_mode=False, gnani_api_key=SimpleNamespace(get_secret_value=lambda: "test"))
        async def reserve_tts(self, room, count): pass
    class Transport:
        async def send_event(self, payload): pass
        async def send_audio(self, payload): pass
    service = TTSService(Manager(), Manager.settings)
    async def partial_sse(key, payload, transport):
        calls.append("sse")
        raise _TTSStreamError("interrupted", audio_started=True)
    async def websocket(key, payload, transport): calls.append("websocket")
    monkeypatch.setattr(service, "_sse", partial_sse)
    monkeypatch.setattr(service, "_websocket", websocket)
    with pytest.raises(_TTSStreamError):
        asyncio.run(service.speak(SimpleNamespace(), Transport(), "Hello", "male", "hi-IN", "neutral"))
    assert calls == ["sse"]
