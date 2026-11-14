from __future__ import annotations

import io
import math
import struct
import wave


SAMPLE_RATE = 16_000
FRAME_SAMPLES = 512
FRAME_BYTES = FRAME_SAMPLES * 2
FRAME_SECONDS = FRAME_SAMPLES / SAMPLE_RATE


def mock_tts_wav(text: str, sample_rate: int = 24_000) -> bytes:
    """Short deterministic audible fixture; text content itself is not logged or stored."""
    duration = min(1.1, max(0.25, len(text) * 0.018))
    frames = int(sample_rate * duration)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        samples = bytearray()
        for index in range(frames):
            sample = int(3500 * math.sin(2 * math.pi * 440 * index / sample_rate))
            samples.extend(struct.pack("<h", sample))
        output.writeframes(samples)
    return buffer.getvalue()
