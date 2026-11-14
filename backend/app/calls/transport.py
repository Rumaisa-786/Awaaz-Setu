from __future__ import annotations

import base64
import asyncio
from collections.abc import Awaitable, Callable
from typing import Protocol
from fastapi import WebSocket


class CalleeTransport(Protocol):
    """Outbound only: callee audio is never forwarded to the user socket."""
    async def send_audio(self, payload: bytes) -> None: ...
    async def send_event(self, payload: dict[str, object]) -> None: ...
    async def close(self) -> None: ...


class WebLinkTransport:
    def __init__(self, websocket: WebSocket, on_first_audio: Callable[[], Awaitable[None]] | None = None):
        self.websocket = websocket
        self.lock = asyncio.Lock()
        self.on_first_audio = on_first_audio
        self.first_audio_sent = False

    async def send_audio(self, payload: bytes) -> None:
        # The browser queues chunk bytes for playback. No user microphone audio reaches this path.
        if not self.first_audio_sent:
            self.first_audio_sent = True
            await self.send_event({"type": "tts_status", "state": "speaking"})
            if self.on_first_audio:
                await self.on_first_audio()
        async with self.lock:
            await self.websocket.send_json({"type": "audio_chunk", "audio": base64.b64encode(payload).decode("ascii")})

    async def send_event(self, payload: dict[str, object]) -> None:
        async with self.lock:
            await self.websocket.send_json(payload)

    async def close(self) -> None:
        try:
            await self.websocket.close()
        except RuntimeError:
            pass
