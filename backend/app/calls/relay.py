from __future__ import annotations

import asyncio
import json
import logging

import websockets
from fastapi import WebSocket

from app.calls.session import CallSession, CallSessionManager
from app.config import Settings, get_settings
from app.entities import analyze_utterance, detect_security_risk, extract_entities
from app.gnani.audio import FRAME_BYTES
from app.llm.tasks import confirm_entities, suggest_replies

logger = logging.getLogger(__name__)


def build_prisma_headers(room: CallSession, settings: Settings) -> dict[str, str]:
    headers = {
        "x-api-key-id": settings.gnani_api_key.get_secret_value(),
        "x-sample-rate": "16000",
        "language_code": room.callee_language or "indic-auto",
        "x-language-code": room.callee_language or "indic-auto",
        "x-format": "transcribe",
        "x-model": "prisma-v3.0",
        "x-partials": "true",
    }
    if room.use_keyterms and room.keyterms:
        headers["x-keyterms"] = json.dumps(room.keyterms[:20], ensure_ascii=False)
    return headers


async def _send_user(room: CallSession, payload: dict[str, object]) -> None:
    socket: WebSocket | None = room.user_socket
    if not socket:
        return
    try:
        async with room.send_lock:
            await socket.send_json(payload)
    except Exception:
        room.user_socket = None


async def process_final_transcript(room: CallSession, text: str, language: str, latency: int | None) -> None:
    if not text.strip():
        return
    room.turns.append({"role": "caller", "text": text})
    await _send_user(room, {"type": "final_transcript", "text": text, "detected_language_code": language, "latency": latency})
    analysis = analyze_utterance(text)
    if analysis["entities"] or analysis["otp_pin_cvv_request"]:
        await _send_user(room, {"type": "entities", **analysis})
    # Suggestions and entity confirmation run independently; neither blocks the caption frame.
    asyncio.create_task(_enrich_final(room, text, language, analysis))


async def _enrich_final(room: CallSession, text: str, language: str, analysis: dict[str, object]) -> None:
    try:
        suggestions, confirmed = await asyncio.gather(
            suggest_replies(text, language or "en-IN", room.goal, room.keyterms if room.use_keyterms else [], room.turns),
            confirm_entities(text, extract_entities(text), bool(analysis["otp_pin_cvv_request"])),
        )
        await _send_user(room, {"type": "suggestions", "replies": suggestions.replies, "needs_free_text": suggestions.needs_free_text, "language": language})
        if confirmed.confirmed_entities or confirmed.risk_request:
            await _send_user(room, {"type": "entity_confirmation", "entities": confirmed.confirmed_entities, "otp_pin_cvv_request": confirmed.risk_request})
    except Exception as exc:
        logger.info("LLM enrichment failed (%s)", type(exc).__name__)


async def run_prisma_relay(room: CallSession, manager: CallSessionManager, settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    if settings.mock_mode:
        await _run_mock_stt(room)
        return
    if not settings.gnani_api_key.get_secret_value():
        room.stt_error = "Gnani STT is not configured"
        await _send_user(room, {"type": "connection_error", "service": "stt", "message": room.stt_error})
        await _drain_audio(room)
        return
    endpoint = settings.gnani_base_url.rstrip("/").replace("https://", "wss://").replace("http://", "ws://") + "/stt/v3/stream"
    while room.state != "ended" and room.age_minutes < settings.call_max_minutes:
        room.settings_changed.clear()
        headers = build_prisma_headers(room, settings)
        try:
            async with websockets.connect(endpoint, additional_headers=headers, open_timeout=8, close_timeout=2, ping_interval=20) as upstream:
                await _send_user(room, {"type": "connection_status", "service": "stt", "state": "connected"})
                sender = asyncio.create_task(_send_frames(room, upstream))
                receiver = asyncio.create_task(_receive_transcripts(room, upstream))
                change = asyncio.create_task(room.settings_changed.wait())
                done, pending = await asyncio.wait({sender, receiver, change}, return_when=asyncio.FIRST_COMPLETED)
                reconnect = change in done and room.state != "ended"
                for task in pending:
                    task.cancel()
                await asyncio.gather(*pending, return_exceptions=True)
                for task in done:
                    if task is not change:
                        task.result()
                if reconnect:
                    await _send_user(room, {"type": "connection_status", "service": "stt", "state": "reconnecting", "reason": "context settings changed"})
                    continue
                if room.state == "ended":
                    break
                raise ConnectionError("Prisma websocket closed")
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            room.stt_error = type(exc).__name__
            await _send_user(room, {"type": "connection_status", "service": "stt", "state": "reconnecting"})
            logger.info("Prisma stream disconnected (%s)", type(exc).__name__)
            await asyncio.sleep(settings.prisma_reconnect_seconds)


async def _send_frames(room: CallSession, upstream: websockets.ClientConnection) -> None:
    while room.state != "ended":
        frame = await room.audio_queue.get()
        if len(frame) != FRAME_BYTES:
            continue
        await upstream.send(frame)
        await asyncio.sleep(0.032)


async def _drain_audio(room: CallSession) -> None:
    while room.state != "ended":
        await room.audio_queue.get()


async def _receive_transcripts(room: CallSession, upstream: websockets.ClientConnection) -> None:
    async for raw in upstream:
        if not isinstance(raw, str):
            continue
        try:
            event = json.loads(raw)
        except json.JSONDecodeError:
            continue
        kind = event.get("type", "")
        if kind in {"partial_transcript", "partial"}:
            await _send_user(room, {"type": "partial_transcript", "stable_text": event.get("stable_text", ""), "volatile_text": event.get("volatile_text", "")})
        elif kind == "final_transcript":
            await process_final_transcript(room, str(event.get("text", "")), str(event.get("detected_language_code", "")), _latency(event))
        elif kind == "transcript":  # Documented Prisma v3 committed-segment schema.
            await process_final_transcript(room, str(event.get("text", "")), str(event.get("detected_language_code", "")), _latency(event))
        elif kind in {"speech_start", "speech_end", "processing"}:
            normalized = "speech_end" if kind == "processing" else kind
            await _send_user(room, {"type": normalized})
        elif kind == "error":
            await _send_user(room, {"type": "connection_error", "service": "stt", "message": "Prisma reported a stream error."})


def _latency(event: dict[str, object]) -> int | None:
    try:
        return int(float(event.get("latency", 0)))
    except (ValueError, TypeError):
        return None


async def _run_mock_stt(room: CallSession) -> None:
    sent = False
    while room.state != "ended":
        frame = await room.audio_queue.get()
        if sent or len(frame) != FRAME_BYTES:
            continue
        sent = True
        if room.callee_language.startswith("ta"):
            sample, language = "வணக்கம், நாளை காலை 10:00 மணிக்கு பேசலாமா?", "ta-IN"
        elif room.callee_language.startswith("kn"):
            sample, language = "ನಾಳೆ ಬೆಳಿಗ್ಗೆ 10:00 ಗಂಟೆಗೆ ಮಾತನಾಡೋಣ", "kn-IN"
        else:
            sample, language = "डॉक्टर का अपॉइंटमेंट कल सुबह 10:00 बजे है। कृपया 5,000 रुपये की पुष्टि करें।", "hi-IN"
        await _send_user(room, {"type": "speech_start"})
        await asyncio.sleep(0.15)
        await _send_user(room, {"type": "partial_transcript", "stable_text": sample[:max(1, len(sample)//2)], "volatile_text": sample[max(1, len(sample)//2):]})
        await asyncio.sleep(0.15)
        await process_final_transcript(room, sample, language, 180)
        await _send_user(room, {"type": "speech_end"})
