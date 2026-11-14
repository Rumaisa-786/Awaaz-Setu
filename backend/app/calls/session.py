from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
import secrets
import time
from typing import Any

from app.calls.tones import Tone
from app.config import Settings, get_settings


@dataclass
class CallSession:
    code: str
    user_token: str
    owner_id: str
    goal: str = ""
    user_language: str = "en-IN"
    callee_language: str = "indic-auto"
    voice: str = "Shivani"
    tone: Tone = Tone.NEUTRAL
    keyterms: list[str] = field(default_factory=list)
    use_keyterms: bool = True
    state: str = "ringing"
    created_at: float = field(default_factory=time.monotonic)
    created_iso: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    user_socket: Any = None
    callee_socket: Any = None
    callee_joined: bool = False
    audio_queue: asyncio.Queue[bytes] = field(default_factory=lambda: asyncio.Queue(maxsize=64))
    user_audio_queue: asyncio.Queue[bytes] = field(default_factory=lambda: asyncio.Queue(maxsize=64))
    settings_changed: asyncio.Event = field(default_factory=asyncio.Event)
    user_mode_changed: asyncio.Event = field(default_factory=asyncio.Event)
    transform_gate: asyncio.Event = field(default_factory=asyncio.Event)
    send_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    expiry_task: asyncio.Task[None] | None = None
    turns: list[dict[str, str]] = field(default_factory=list)
    tts_chars: int = 0
    stt_error: str | None = None
    detected_language: str = ""
    input_mode: str = "type"
    save_history: bool = False
    persisted_transcript: list[dict[str, str]] = field(default_factory=list)
    summary: dict[str, Any] | None = None
    direct_audio: bool = False
    transform_review: bool = True

    def __post_init__(self) -> None:
        self.transform_gate.set()

    @property
    def age_minutes(self) -> float:
        return (time.monotonic() - self.created_at) / 60


class CallSessionManager:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.sessions: dict[str, CallSession] = {}
        self.lock = asyncio.Lock()
        self.daily_tts_chars: dict[tuple[str, str], int] = {}

    async def create(self, owner_id: str, **values: Any) -> CallSession:
        async with self.lock:
            self._expire_locked()
            active = sum(room.state != "ended" for room in self.sessions.values())
            if active >= self.settings.max_concurrent_calls:
                raise CallLimitExceeded("Maximum concurrent calls reached")
            code = secrets.token_urlsafe(6)
            while code in self.sessions:
                code = secrets.token_urlsafe(6)
            room = CallSession(code=code, user_token=secrets.token_urlsafe(24), owner_id=owner_id, **values)
            self.sessions[code] = room
            return room

    async def get(self, code: str) -> CallSession | None:
        async with self.lock:
            room = self.sessions.get(code)
            if room and room.age_minutes >= min(self.settings.call_max_minutes, self.settings.session_duration_minutes_limit):
                room.state = "ended"
            return room

    async def end(self, code: str, user_token: str | None = None) -> CallSession | None:
        room = await self.get(code)
        if not room:
            return None
        if user_token is not None and not secrets.compare_digest(room.user_token, user_token):
            raise PermissionError("Invalid call owner token")
        room.state = "ended"
        return room

    async def reserve_tts(self, room: CallSession, char_count: int) -> None:
        day = datetime.now(timezone.utc).date().isoformat()
        key = (room.owner_id, day)
        async with self.lock:
            used = self.daily_tts_chars.get(key, 0)
            if char_count <= 0 or room.tts_chars + char_count > self.settings.tts_session_char_limit:
                raise CallLimitExceeded("This call has reached its speech budget")
            if used + char_count > self.settings.tts_daily_char_limit:
                raise CallLimitExceeded("The daily speech budget has been reached")
            self.daily_tts_chars[key] = used + char_count
            room.tts_chars += char_count

    def _expire_locked(self) -> None:
        maximum = min(self.settings.call_max_minutes, self.settings.session_duration_minutes_limit)
        for room in self.sessions.values():
            if room.state != "ended" and room.age_minutes >= maximum:
                room.state = "ended"


class CallLimitExceeded(RuntimeError):
    pass


manager = CallSessionManager()
