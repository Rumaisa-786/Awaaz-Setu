from __future__ import annotations

import asyncio
import secrets
import time
from typing import Any

from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field, field_validator

from app.calls.relay import run_prisma_relay, run_user_transform, speak_reviewed_transform
from app.calls.session import CallLimitExceeded, CallSession, manager
from app.calls.tones import ALL_VOICES, Tone
from app.calls.transport import WebLinkTransport
from app.auth import resolve_user
from app.config import get_settings
from app.gnani.audio import FRAME_BYTES
from app.gnani.tts import TTSService
from app.llm.tasks import relay_reply, summarize_call

router = APIRouter()
tts_service = TTSService(manager)


class CreateCallRequest(BaseModel):
    goal: str = Field(default="", max_length=500)
    user_language: str = "en-IN"
    callee_language: str = "indic-auto"
    voice: str = "Shivani"
    tone: Tone = Tone.NEUTRAL
    keyterms: list[str] = Field(default_factory=list, max_length=20)
    use_keyterms: bool = True

    @field_validator("user_language")
    @classmethod
    def supported_user_language(cls, value: str) -> str:
        if value not in {"bn-IN", "en-IN", "gu-IN", "hi-IN", "kn-IN", "ml-IN", "mr-IN", "pa-IN", "ta-IN", "te-IN"}:
            raise ValueError("Unsupported user language")
        return value

    @field_validator("callee_language")
    @classmethod
    def supported_callee_language(cls, value: str) -> str:
        if value not in {"indic-auto", "bn-IN", "en-IN", "gu-IN", "hi-IN", "kn-IN", "ml-IN", "mr-IN", "pa-IN", "ta-IN", "te-IN"}:
            raise ValueError("Unsupported caller language hint")
        return value


class EndCallRequest(BaseModel):
    user_token: str
    save_history: bool = False


def _public_room(room: CallSession) -> dict[str, Any]:
    return {"code": room.code, "state": room.state, "goal": room.goal, "created_at": room.created_iso, "callee_connected": room.callee_socket is not None}


@router.post("/api/calls", status_code=201)
async def create_call(payload: CreateCallRequest, request: Request) -> dict[str, object]:
    if payload.voice not in ALL_VOICES:
        raise HTTPException(422, "Unsupported Timbre v3.0 voice")
    if any("<|" in term or "|>" in term for term in payload.keyterms):
        raise HTTPException(422, "Keyterms contain an invalid marker")
    try:
        room = await manager.create(
            owner_id=await resolve_user(request),
            goal=payload.goal.strip(),
            user_language=payload.user_language,
            callee_language=payload.callee_language,
            voice=payload.voice,
            tone=payload.tone,
            keyterms=[term.strip()[:80] for term in payload.keyterms if term.strip()],
            use_keyterms=payload.use_keyterms,
        )
    except CallLimitExceeded as exc:
        raise HTTPException(429, str(exc)) from exc
    room.expiry_task = asyncio.create_task(_expire_call(room))
    return {**_public_room(room), "user_token": room.user_token, "join_path": f"/join/{room.code}"}


@router.get("/api/calls/{code}")
async def get_call(code: str) -> dict[str, object]:
    room = await manager.get(code)
    if not room:
        raise HTTPException(404, "Call not found")
    return _public_room(room)


@router.post("/api/calls/{code}/end")
async def end_call(code: str, request: EndCallRequest) -> dict[str, Any]:
    try:
        room = await manager.end(code, request.user_token)
    except PermissionError as exc:
        raise HTTPException(403, "Only the call owner can end this call") from exc
    if not room:
        raise HTTPException(404, "Call not found")
    room.save_history = request.save_history
    room.summary = (await summarize_call(room.turns, room.user_language)).model_dump()
    if room.save_history:
        room.persisted_transcript = room.turns.copy()
    await _notify_end(room)
    return {"state": "ended", "summary": room.summary, "saved": room.save_history}


async def _notify_end(room: CallSession) -> None:
    for socket in (room.user_socket, room.callee_socket):
        if socket:
            try:
                await socket.send_json({"type": "call_ended"})
            except Exception:
                pass
    room.settings_changed.set()
    room.turns.clear()
    if room.expiry_task and room.expiry_task is not asyncio.current_task():
        room.expiry_task.cancel()


async def _expire_call(room: CallSession) -> None:
    duration = min(manager.settings.call_max_minutes, manager.settings.session_duration_minutes_limit) * 60
    try:
        await asyncio.sleep(max(0, duration - time.monotonic() + room.created_at))
        if room.state != "ended":
            room.state = "ended"
            await _notify_end(room)
    except asyncio.CancelledError:
        return


@router.websocket("/ws/call/user/{code}")
async def user_channel(websocket: WebSocket, code: str) -> None:
    await websocket.accept()
    room = await manager.get(code)
    if not room or room.state == "ended":
        await websocket.close(code=4404)
        return
    try:
        auth = await asyncio.wait_for(websocket.receive_json(), timeout=5)
        token = str(auth.get("token", "")) if auth.get("type") == "auth" else ""
        if not secrets.compare_digest(token, room.user_token):
            await websocket.close(code=4403)
            return
        room.user_socket = websocket
        transform_task = asyncio.create_task(run_user_transform(room, manager))
        await websocket.send_json({"type": "connected", "channel": "user", "mock_mode": get_settings().mock_mode, "state": room.state})
        if room.turns:
            await websocket.send_json({"type": "transcript_history", "turns": room.turns[-50:]})
        while room.state != "ended":
            packet = await websocket.receive()
            if packet.get("type") == "websocket.disconnect":
                break
            if packet.get("bytes") is not None:
                data = packet["bytes"]
                if len(data) != FRAME_BYTES:
                    await _send_room(room, {"type": "error", "message": "Audio frames must contain exactly 1,024 bytes."})
                elif room.input_mode == "direct":
                    if room.callee_socket:
                        await room.callee_socket.send_bytes(data)
                elif room.input_mode == "transform" and room.transform_gate.is_set():
                    try:
                        room.user_audio_queue.put_nowait(data)
                    except asyncio.QueueFull:
                        pass
                continue
            try:
                message = __import__("json").loads(packet.get("text") or "{}")
            except ValueError:
                continue
            await _handle_user_message(room, message)
    except (WebSocketDisconnect, asyncio.TimeoutError):
        pass
    finally:
        if 'transform_task' in locals():
            transform_task.cancel()
            await asyncio.gather(transform_task, return_exceptions=True)
        if room.user_socket is websocket:
            room.user_socket = None


async def _handle_user_message(room: CallSession, message: dict[str, Any]) -> None:
    kind = message.get("type")
    if kind == "typing":
        if room.callee_socket:
            await WebLinkTransport(room.callee_socket).send_event({"type": "user_status", "state": "typing"})
        return
    if kind == "context_settings":
        room.use_keyterms = bool(message.get("use_keyterms", room.use_keyterms))
        if "keyterms" in message and isinstance(message["keyterms"], list):
            room.keyterms = [str(value).strip()[:80] for value in message["keyterms"][:20] if str(value).strip()]
        room.settings_changed.set()
        await _send_room(room, {"type": "context_settings", "use_keyterms": room.use_keyterms})
        return
    if kind == "tone_settings":
        try:
            room.tone = Tone(message.get("tone", room.tone.value))
        except ValueError:
            await _send_room(room, {"type": "error", "message": "Choose one of the available tones."})
            return
        voice = message.get("voice")
        if voice in ALL_VOICES:
            room.voice = voice
        return
    if kind == "input_mode":
        mode = message.get("mode")
        if mode not in {"type", "direct", "transform"}:
            await _send_room(room, {"type": "error", "message": "Choose one of the available input modes."})
            return
        if room.input_mode != mode:
            room.input_mode = mode
            room.direct_audio = mode == "direct"
            room.user_mode_changed.set()
        await _send_room(room, {"type": "input_mode", "mode": mode})
        return
    if kind == "transform_settings":
        room.transform_review = message.get("behavior", "review") != "auto"
        await _send_room(room, {"type": "transform_settings", "behavior": "review" if room.transform_review else "auto"})
        return
    if kind == "send_transform":
        text = str(message.get("text", "")).strip()
        if text and len(text) <= 1000:
            await speak_reviewed_transform(room, text)
        return
    if kind == "language_override":
        language = str(message.get("language", ""))
        if language in {"bn-IN", "en-IN", "gu-IN", "hi-IN", "kn-IN", "ml-IN", "mr-IN", "pa-IN", "ta-IN", "te-IN"}:
            room.detected_language = language
            room.callee_language = language
            room.settings_changed.set()
            await _send_room(room, {"type": "language", "language": language, "manual": True})
        return
    if kind == "end_call":
        await manager.end(room.code, room.user_token)
        await _notify_end(room)
        return
    if kind not in {"send_text", "preview_tone"}:
        await _send_room(room, {"type": "error", "message": "Unsupported call action."})
        return
    text = str(message.get("text", "")).strip()
    if not text or len(text) > 1000:
        await _send_room(room, {"type": "error", "message": "Replies must be between 1 and 1,000 characters."})
        return
    try:
        tone = Tone(message.get("tone", room.tone.value))
    except ValueError:
        tone = room.tone
    source_language = str(message.get("language", room.user_language))
    rewrite = await relay_reply(text, source_language, room.detected_language or room.callee_language, tone)
    if kind == "preview_tone":
        await _send_room(room, {"type": "tone_preview", "text": rewrite.rewritten_text, "tone": tone.value})
        return
    room.turns.append({"role": "user", "text": text, "translated_text": rewrite.rewritten_text})
    await _send_room(room, {"type": "user_reply", "text": text, "spoken_text": rewrite.rewritten_text, "language": room.detected_language or room.callee_language})
    callee = room.callee_socket
    if not callee:
        await _send_room(room, {"type": "error", "message": "The other caller has not joined yet."})
        return
    transport = WebLinkTransport(callee, on_first_audio=lambda: _send_room(room, {"type": "tts_status", "state": "speaking"}))
    await _send_room(room, {"type": "tts_status", "state": "synthesizing"})
    try:
        await tts_service.speak(room, transport, rewrite.rewritten_text, room.voice, room.detected_language or room.callee_language, tone, rewrite.audio_tag)
        await transport.send_event({"type": "user_status", "state": "delivered"})
        await _send_room(room, {"type": "tts_status", "state": "delivered"})
    except Exception as exc:
        await _send_room(room, {"type": "tts_status", "state": "failed"})
        await _send_room(room, {"type": "error", "message": "Speech could not be sent. Your reply remains available as text."})


async def _send_room(room: CallSession, payload: dict[str, object]) -> None:
    socket = room.user_socket
    if socket:
        try:
            await socket.send_json(payload)
        except Exception:
            room.user_socket = None


@router.websocket("/ws/call/callee/{code}")
async def callee_channel(websocket: WebSocket, code: str) -> None:
    await websocket.accept()
    room = await manager.get(code)
    if not room or room.state == "ended" or room.callee_joined:
        await websocket.close(code=4404 if not room else 4409)
        return
    room.callee_joined = True
    room.callee_socket = websocket
    room.state = "live"
    await websocket.send_json({"type": "connected", "channel": "callee", "sample_rate": 16_000, "frame_bytes": FRAME_BYTES})
    await _send_room(room, {"type": "callee_status", "state": "connected"})
    relay = asyncio.create_task(run_prisma_relay(room, manager))
    try:
        while room.state != "ended":
            packet = await websocket.receive()
            if packet.get("type") == "websocket.disconnect":
                break
            data = packet.get("bytes")
            if data is not None:
                if len(data) != FRAME_BYTES:
                    await websocket.send_json({"type": "error", "message": "Audio frames must contain exactly 1,024 bytes."})
                    continue
                try:
                    # This socket is exclusively callee -> Prisma -> captions.
                    # User mic frames enter through the separately authenticated user socket.
                    room.audio_queue.put_nowait(data)
                except asyncio.QueueFull:
                    # Keep microphone capture responsive through a short upstream outage.
                    try:
                        room.audio_queue.get_nowait()
                        room.audio_queue.put_nowait(data)
                    except asyncio.QueueEmpty:
                        pass
            elif packet.get("text"):
                try:
                    control = __import__("json").loads(packet["text"])
                except ValueError:
                    continue
                if control.get("type") == "leave":
                    break
    except WebSocketDisconnect:
        pass
    finally:
        room.callee_socket = None
        if room.state != "ended":
            room.state = "ended"
            await _send_room(room, {"type": "call_ended", "reason": "callee_disconnected"})
        room.turns.clear()
        if room.expiry_task:
            room.expiry_task.cancel()
        room.settings_changed.set()
        relay.cancel()
        await asyncio.gather(relay, return_exceptions=True)
