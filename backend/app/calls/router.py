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
from app.entities import analyze_utterance

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


class GateDemoRequest(BaseModel):
    user_language: str = "en-IN"
    voice: str = "Shivani"

    @field_validator("user_language")
    @classmethod
    def validate_language(cls, value: str) -> str:
        if value not in {"bn-IN", "en-IN", "gu-IN", "hi-IN", "kn-IN", "ml-IN", "mr-IN", "pa-IN", "ta-IN", "te-IN"}:
            raise ValueError("Unsupported user language")
        return value


def _public_room(room: CallSession) -> dict[str, Any]:
    return {"code": room.code, "state": room.state, "goal": room.goal, "created_at": room.created_iso, "callee_connected": room.callee_socket is not None, "gate_demo": room.gate_demo}


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


@router.post("/api/demo/gate", status_code=201)
async def create_gate_demo(payload: GateDemoRequest, request: Request) -> dict[str, object]:
    if payload.voice not in ALL_VOICES:
        raise HTTPException(422, "Unsupported Timbre v3.0 voice")
    try:
        room = await manager.create(owner_id=await resolve_user(request), goal="Scripted demo: simulated delivery at the main gate", user_language=payload.user_language, callee_language="hi-IN", voice=payload.voice, tone=Tone.POLITE, keyterms=["Blinkit", "Ramesh", "₹450", "main gate"], use_keyterms=True)
    except CallLimitExceeded as exc:
        raise HTTPException(429, str(exc)) from exc
    room.gate_demo = True
    room.callee_joined = True
    room.callee_socket = GateDemoBridge(room)
    room.state = "live"
    room.expiry_task = asyncio.create_task(_expire_call(room))
    return {**_public_room(room), "user_token": room.user_token, "join_path": f"/call/{room.code}"}


class GateDemoBridge:
    """Virtual callee for the explicitly scripted delivery scene; only returns demo TTS to user UI."""
    def __init__(self, room: CallSession):
        self.room = room

    async def send_json(self, payload: dict[str, Any]) -> None:
        socket = self.room.user_socket
        if socket:
            async with self.room.send_lock:
                await socket.send_json(payload)


async def _send_gate_demo_speech(room: CallSession, text: str, language: str) -> None:
    bridge = room.callee_socket
    if not isinstance(bridge, GateDemoBridge):
        return
    try:
        async with room.tts_lock:
            await _send_room(room, {"type": "demo_speech", "text": text})
            await tts_service.speak(room, WebLinkTransport(bridge), text, room.voice, language, room.tone)
    except Exception as exc:
        await _send_room(room, {"type": "service_status", "service": "tts", "state": "fallback", "reason": type(exc).__name__})


async def _run_gate_demo(room: CallSession) -> None:
    disclosure = "Hi, I am using Awaaz Setu live captions to read your message. This is a scripted delivery demo. The call is not recorded."
    caller_text = "नमस्ते, मैं मेन गेट पर हूँ, आपका पार्सल आया है, ₹450 कैश ऑन डिलीवरी है, गेट कोड बता दीजिए।"
    await _send_room(room, {"type": "demo_banner", "title": "Scripted Demo Scenario — Simulated Delivery Caller", "caller": "Ramesh — Blinkit / Courier at Main Gate"})
    await _send_room(room, {"type": "demo_disclosure", "text": disclosure})
    await _send_room(room, {"type": "demo_speech", "text": caller_text})
    room.detected_language = "hi-IN"
    room.turns.append({"role": "caller", "text": caller_text})
    await _send_room(room, {"type": "final_transcript", "text": caller_text, "translated_text": caller_text, "detected_language_code": "hi-IN", "latency": None, "turn_index": len(room.turns) - 1, "demo": True})
    entities = analyze_utterance(caller_text)
    entities["otp_pin_cvv_request"] = True  # Script explicitly asks for a gate code.
    await _send_room(room, {"type": "entities", **entities})
    await _send_room(room, {"type": "suggestions", "language": room.user_language, "replies": ["Please leave it with the security guard", "I am coming down in 2 minutes", "Please share the QR code for UPI payment"]})
    room.gate_audio_task = asyncio.create_task(_speak_gate_sequence(room, disclosure, caller_text))


async def _speak_gate_sequence(room: CallSession, disclosure: str, caller_text: str) -> None:
    await _send_gate_demo_speech(room, disclosure, "en-IN")
    if room.state != "ended":
        await _send_gate_demo_speech(room, caller_text, "hi-IN")


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
    sockets = (room.user_socket,) if isinstance(room.callee_socket, GateDemoBridge) else (room.user_socket, room.callee_socket)
    for socket in sockets:
        if socket:
            try:
                await socket.send_json({"type": "call_ended"})
            except Exception:
                pass
    room.settings_changed.set()
    room.turns.clear()
    cancelled: list[asyncio.Task[Any]] = []
    if room.gate_audio_task and room.gate_audio_task is not asyncio.current_task():
        cancelled.append(room.gate_audio_task)
    cancelled.extend(task for task in room.tts_tasks if task is not asyncio.current_task())
    for task in cancelled:
        task.cancel()
    room.tts_tasks.clear()
    if cancelled:
        await asyncio.gather(*cancelled, return_exceptions=True)
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
        if room.gate_demo:
            room.callee_socket = GateDemoBridge(room)
            room.callee_joined = True
        transform_task = asyncio.create_task(run_user_transform(room, manager))
        await websocket.send_json({"type": "connected", "channel": "user", "mock_mode": get_settings().mock_mode, "state": room.state, "gate_demo": room.gate_demo})
        if room.gate_demo:
            await _send_room(room, {"type": "callee_status", "state": "connected"})
            room.gate_audio_task = asyncio.create_task(_run_gate_demo(room))
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
    if rewrite.uncertainty:
        await _send_room(room, {"type": "service_status", "service": "llm", "state": "fallback"})
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
    if room.gate_demo:
        task = asyncio.create_task(_speak_gate_reply(room, transport, rewrite.rewritten_text, tone, rewrite.audio_tag))
        room.tts_tasks.add(task)
        task.add_done_callback(room.tts_tasks.discard)
        return
    try:
        await tts_service.speak(room, transport, rewrite.rewritten_text, room.voice, room.detected_language or room.callee_language, tone, rewrite.audio_tag)
        await transport.send_event({"type": "user_status", "state": "delivered"})
        await _send_room(room, {"type": "tts_status", "state": "delivered"})
    except Exception as exc:
        await _send_room(room, {"type": "tts_status", "state": "failed"})
        await _send_room(room, {"type": "error", "message": "Speech could not be sent. Your reply remains available as text."})


async def _speak_gate_reply(room: CallSession, transport: WebLinkTransport, text: str, tone: Tone, tag: str | None) -> None:
    try:
        async with room.tts_lock:
            await tts_service.speak(room, transport, text, room.voice, room.detected_language or "hi-IN", tone, tag)
        await _send_room(room, {"type": "tts_status", "state": "delivered"})
    except Exception as exc:
        await _send_room(room, {"type": "service_status", "service": "tts", "state": "fallback", "reason": type(exc).__name__})
        await _send_room(room, {"type": "error", "message": "Demo speech could not be played. The scripted captions are still available."})


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
    if not room or room.state == "ended" or room.callee_socket is not None:
        await websocket.close(code=4404 if not room else 4409)
        return
    room.callee_joined = True
    room.callee_socket = websocket
    room.state = "live"
    await websocket.send_json({"type": "connected", "channel": "callee", "sample_rate": 16_000, "frame_bytes": FRAME_BYTES})
    await _send_room(room, {"type": "callee_status", "state": "connected"})
    relay = asyncio.create_task(run_prisma_relay(room, manager))
    explicit_leave = False
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
                    explicit_leave = True
                    break
    except WebSocketDisconnect:
        pass
    finally:
        room.callee_socket = None
        if explicit_leave and room.state != "ended":
            room.state = "ended"
            await _notify_end(room)
        elif room.state != "ended":
            await _send_room(room, {"type": "callee_status", "state": "reconnecting"})
        room.settings_changed.set()
        relay.cancel()
        await asyncio.gather(relay, return_exceptions=True)
