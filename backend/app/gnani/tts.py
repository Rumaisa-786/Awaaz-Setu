from __future__ import annotations

import base64
import json
import logging

import httpx
import websockets

from app.calls.session import CallSession, CallSessionManager
from app.calls.tones import ALL_VOICES, Tone, sanitize_tts_text
from app.calls.transport import CalleeTransport
from app.config import Settings, get_settings
from app.gnani.audio import mock_tts_wav

logger = logging.getLogger(__name__)


def _strip_repeated_wav_header(chunk: bytes, first_chunk: bool) -> bytes:
    """Timbre SSE repeats a 44-byte RIFF/WAV header on chunks after the first."""
    if not first_chunk and chunk.startswith(b"RIFF") and chunk[8:12] == b"WAVE":
        return chunk[44:]
    return chunk


class TTSService:
    def __init__(self, manager: CallSessionManager, settings: Settings | None = None):
        self.manager = manager
        self.settings = settings or get_settings()

    async def speak(self, room: CallSession, transport: CalleeTransport, text: str, voice: str, language: str, tone: Tone, candidate_tag: str | None = None) -> None:
        safe_text = sanitize_tts_text(text, tone, candidate_tag)
        if not safe_text:
            raise ValueError("Reply text is empty after removing unsupported markup")
        selected_voice = voice if voice in ALL_VOICES else "Shivani"
        await self.manager.reserve_tts(room, len(safe_text))
        await transport.send_event({"type": "tts_status", "state": "synthesizing"})
        if self.settings.mock_mode:
            await transport.send_audio(mock_tts_wav(safe_text))
        else:
            key = self.settings.gnani_api_key.get_secret_value()
            if not key:
                raise RuntimeError("Gnani is not configured")
            await self._websocket_or_sse(key, safe_text, selected_voice, language, transport)
        await transport.send_event({"type": "tts_complete"})

    async def _websocket_or_sse(self, key: str, text: str, voice: str, language: str, transport: CalleeTransport) -> None:
        payload = {
            "text": text,
            "voice": voice,
            "model": "timbre-v3.0",
            "language": language or "auto",
            "audio_config": {"sample_rate": 24_000, "encoding": "linear_pcm", "container": "wav"},
        }
        ws_url = self.settings.gnani_base_url.rstrip("/").replace("https://", "wss://").replace("http://", "ws://") + "/api/v1/tts"
        audio_sent = False
        try:
            async with websockets.connect(ws_url, additional_headers={"X-API-Key-ID": key, "Content-Type": "application/json"}, open_timeout=8, close_timeout=2) as socket:
                await socket.send(json.dumps(payload, ensure_ascii=False))
                async for raw in socket:
                    if not isinstance(raw, str):
                        await transport.send_audio(bytes(raw))
                        audio_sent = True
                        continue
                    message = json.loads(raw)
                    if message.get("type") == "error":
                        raise RuntimeError("Timbre realtime returned an error")
                    data = message.get("data", message)
                    encoded = data.get("audio", "") if isinstance(data, dict) else ""
                    if encoded:
                        await transport.send_audio(base64.b64decode(encoded))
                        audio_sent = True
                    if message.get("type") == "complete" or data.get("is_final"):
                        if not audio_sent:
                            raise RuntimeError("Timbre realtime completed without audio")
                        return
            raise RuntimeError("Timbre realtime ended without audio completion")
        except Exception as exc:
            logger.info("Timbre realtime unavailable (%s); trying SSE fallback", type(exc).__name__)
            if audio_sent:
                raise RuntimeError("Timbre realtime interrupted after streaming audio") from exc
            await self._sse(key, payload, transport)

    async def _sse(self, key: str, payload: dict[str, object], transport: CalleeTransport) -> None:
        endpoint = self.settings.gnani_base_url.rstrip("/") + "/api/v1/tts/sse"
        first_audio_chunk = True
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=8.0)) as client:
            async with client.stream("POST", endpoint, headers={"X-API-Key-ID": key}, json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    content = line[5:].strip()
                    if not content:
                        continue
                    event = json.loads(content)
                    encoded = event.get("audio", "")
                    if encoded:
                        chunk = base64.b64decode(encoded)
                        chunk = _strip_repeated_wav_header(chunk, first_audio_chunk)
                        first_audio_chunk = False
                        await transport.send_audio(chunk)
                    if event.get("is_final"):
                        return
