"""Human-run M0 live API probes. Never prints credentials; not part of pytest."""
from __future__ import annotations

import asyncio
import json
import os
import time
import wave
from pathlib import Path

import httpx
from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
import websockets

ROOT = Path(__file__).resolve().parents[2]
TMP = ROOT / "tmp"
BASE = "https://api.vachana.ai"
TAGS = ["<coughs>", "<excited>", "<exhales>", "<giggle>", "<laugh>", "<pauses>", "<shouting>", "<sigh>", "<slow>", "<sniffles>", "<whispers>", "<yawns>", "<clears throat>"]
VOICES = ["Shivani", "Chetana", "Tarika"]


class Suggestions(BaseModel):
    replies: list[str] = Field(max_length=4)
    needs_free_text: bool


class Translation(BaseModel):
    translated_text: str
    uncertain: bool


class ToneRewrite(BaseModel):
    rewritten_text: str
    audio_tag: str | None


class Summary(BaseModel):
    outcomes: list[str]
    open_items: list[str]
    plain_language_summary: str


def env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def require_keys() -> tuple[str, str]:
    gnani, gemini = env("GNANI_API_KEY"), env("GEMINI_API_KEY")
    absent = [key for key, value in (("GNANI_API_KEY", gnani), ("GEMINI_API_KEY", gemini)) if not value]
    if absent:
        raise SystemExit("Set required values in .env: " + ", ".join(absent))
    return gnani, gemini


def speech_fixture(key: str) -> Path:
    path = TMP / "smoke-generated-hi.wav"
    response = httpx.post(BASE + "/api/v1/tts/inference", headers={"X-API-Key-ID": key}, json={"text": "नमस्ते, डॉक्टर का अपॉइंटमेंट कल सुबह दस बजे है। कृपया पाँच लाख रुपये की पुष्टि करें।", "voice": "Shivani", "model": "timbre-v3.0", "language": "hi-IN", "audio_config": {"sample_rate": 16000, "num_channels": 1, "sample_width": 2, "encoding": "linear_pcm", "container": "wav"}}, timeout=60)
    response.raise_for_status()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(response.content)
    print(json.dumps({"generated_stt_fixture": str(Path("tmp") / path.name), "format": wav_info(response.content)}))
    return path


def stt_rest(key: str, clip: Path) -> None:
    print("\n== Prisma REST ==")
    for language, fmt in (("indic-auto", "verbatim"), ("hi-IN", "transcribe"), ("ta-IN", "transcribe"), ("kn-IN", "transcribe")):
        started = time.perf_counter()
        with clip.open("rb") as audio:
            response = httpx.post(BASE + "/stt/v3", headers={"X-API-Key-ID": key}, files={"audio_file": (clip.name, audio, "audio/wav")}, data={"model": "prisma-v3.0", "language_code": language, "format": fmt}, timeout=60)
        print(json.dumps({"language": language, "format": fmt, "status": response.status_code, "elapsed_s": round(time.perf_counter()-started, 3), "result": response.json() if response.is_success else response.text[:1000]}, ensure_ascii=False))


async def stt_stream(key: str, clip: Path) -> None:
    print("\n== Prisma realtime probes ==")
    with wave.open(str(clip), "rb") as audio:
        source_rate = audio.getframerate(); channels = audio.getnchannels(); width = audio.getsampwidth(); pcm = audio.readframes(audio.getnframes())
    if channels != 1 or width != 2 or source_rate not in {8000, 16000}:
        raise ValueError("SMOKE_AUDIO_FILE must be mono PCM16 WAV at 8 kHz or 16 kHz")
    if source_rate == 8000:
        pcm_by_rate = {8000: pcm, 16000: b"".join(pcm[i:i+2] * 2 for i in range(0, len(pcm), 2))}
    else:
        pcm_by_rate = {16000: pcm, 8000: b"".join(pcm[i:i+2] for i in range(0, len(pcm), 4))}
    probes = (("model-header", {}), ("without-model-header", {"x-model": None}), ("keyterms", {"x-keyterms": json.dumps(["clinic", "appointment"], ensure_ascii=True)}), ("bias-list-score", {"x-bias-list": '["clinic", "appointment"]', "x-bias-score": "1.0"}), ("partials", {"x-partials": "true"}))
    for rate, pcm in pcm_by_rate.items():
      pace = 0.032 if rate == 16000 else 0.064
      for label, extra in probes:
        headers = {"x-api-key-id": key, "language_code": "indic-auto", "x-sample-rate": str(rate), "x-format": "transcribe", "x-model": "prisma-v3.0", **extra}
        if headers.get("x-model") is None: del headers["x-model"]
        t0 = time.perf_counter()
        try:
            async with websockets.connect(BASE.replace("https://", "wss://") + "/stt/v3/stream", additional_headers=headers, open_timeout=15) as ws:
                print(json.dumps({"probe": label, "sample_rate": rate, "frame_bytes": 1024, "frame_pace_ms": pace * 1000, "handshake_s": round(time.perf_counter()-t0, 3), "connected": True}))
                for offset in range(0, len(pcm), 1024):
                    frame = pcm[offset:offset+1024]
                    if len(frame) < 1024: frame += bytes(1024-len(frame))
                    await ws.send(frame); await asyncio.sleep(pace)
                # Silence frames trigger Prisma VAD; there is no JSON commit command.
                for _ in range(16):
                    await ws.send(bytes(1024)); await asyncio.sleep(pace)
                saw_speech_end = False
                async with asyncio.timeout(15):
                    while True:
                        msg = await ws.recv()
                        if not isinstance(msg, str): continue
                        event = json.loads(msg)
                        print(json.dumps({"probe": label, "message": event}))
                        if event.get("type") == "speech_end": saw_speech_end = True
                        if saw_speech_end and event.get("type") in {"transcript", "final_transcript"}: break
        except Exception as exc:
            print(json.dumps({"probe": label, "sample_rate": rate, "error_type": type(exc).__name__}))


def wav_info(payload: bytes) -> dict[str, int | str]:
    with wave.open(__import__("io").BytesIO(payload), "rb") as audio:
        return {"format": "WAV/PCM" if audio.getcomptype() == "NONE" else audio.getcomptype(), "sample_rate": audio.getframerate(), "channels": audio.getnchannels(), "sample_width_bytes": audio.getsampwidth()}


def tts(key: str) -> None:
    print("\n== Timbre REST and tag auditions ==")
    dest = TMP / "tts-auditions"; dest.mkdir(parents=True, exist_ok=True)
    samples = (("hi-IN", "नमस्ते, मैं आपकी सहायता के लिए यहाँ हूँ।"), ("ta-IN", "வணக்கம், நான் உங்களுக்கு உதவ வந்துள்ளேன்."), ("en-IN", "Hello, I am here to help you."))
    for lang, text in samples:
        started = time.perf_counter()
        with httpx.stream("POST", BASE + "/api/v1/tts/inference", headers={"X-API-Key-ID": key}, json={"text": text, "voice": "Shivani", "model": "timbre-v3.0", "language": lang, "audio_config": {"sample_rate": 24000, "num_channels": 1, "sample_width": 2, "encoding": "linear_pcm", "container": "wav"}}, timeout=60) as response:
            chunks = []; first = None
            for chunk in response.iter_bytes():
                if chunk:
                    first = first or time.perf_counter()-started
                    chunks.append(chunk)
            content = b"".join(chunks)
            if response.is_success:
                path = dest / f"neutral-{lang}.wav"; path.write_bytes(content)
                info = wav_info(content)
            else: info = {"error_status": response.status_code}
            print(json.dumps({"lang": lang, "status": response.status_code, "first_byte_latency_s": round(first, 3) if first else None, "response_content_type": response.headers.get("content-type"), "audio": info}))
    audition_text = "Hello, thank you for calling."
    for voice in VOICES:
        for tag in TAGS:
            response = httpx.post(BASE + "/api/v1/tts/inference", headers={"X-API-Key-ID": key}, json={"text": f"{tag} {audition_text}", "voice": voice, "model": "timbre-v3.0", "language": "en-IN", "audio_config": {"sample_rate": 24000, "encoding": "linear_pcm", "container": "wav"}}, timeout=60)
            filename = f"{voice.lower()}-{tag[1:-1].replace(' ', '-')}.wav"
            if response.is_success: (dest / filename).write_bytes(response.content)
            print(json.dumps({"voice": voice, "tag": tag, "status": response.status_code, "file": str(Path("tmp") / "tts-auditions" / filename) if response.is_success else None}))

    # Streaming probes use the same short utterance to compare first-byte behavior.
    payload = {"text": "Hello, I am here to help you.", "voice": "Shivani", "model": "timbre-v3.0", "language": "en-IN", "audio_config": {"sample_rate": 24000, "encoding": "linear_pcm", "container": "wav"}}
    for mode, endpoint in (("sse", "/api/v1/tts/sse"),):
        started = time.perf_counter(); first = None; event_count = 0
        with httpx.stream("POST", BASE + endpoint, headers={"X-API-Key-ID": key}, json=payload, timeout=90) as response:
            for line in response.iter_lines():
                if line:
                    first = first or time.perf_counter() - started
                    event_count += 1
            print(json.dumps({"mode": mode, "status": response.status_code, "first_byte_latency_s": round(first, 3) if first else None, "events": event_count, "content_type": response.headers.get("content-type")}))
    # WS responses are JSON messages carrying base64 audio chunks per the API guide.
    async def tts_ws_probe() -> None:
        started = time.perf_counter(); first_audio = None; chunks = 0
        try:
            async with websockets.connect("wss://api.vachana.ai/api/v1/tts", additional_headers={"X-API-Key-ID": key, "Content-Type": "application/json"}, open_timeout=15) as ws:
                await ws.send(json.dumps(payload))
                async for message in ws:
                    if isinstance(message, str):
                        event = json.loads(message)
                        if event.get("type") == "audio":
                            first_audio = first_audio or time.perf_counter() - started
                            chunks += 1
                        if event.get("type") in {"complete", "error"}:
                            print(json.dumps({"mode": "websocket", "event": event.get("type"), "first_audio_latency_s": round(first_audio, 3) if first_audio else None, "audio_chunks": chunks}))
                            break
        except Exception as exc:
            print(json.dumps({"mode": "websocket", "error_type": type(exc).__name__}))
    asyncio.run(tts_ws_probe())


def llm_bakeoff(api_key: str) -> None:
    print("\n== Gemini bake-off ==")
    client = genai.Client(api_key=api_key)
    model = env("LLM_MODEL", "gemini-3.5-flash-lite")
    tests = [
        ("suggest_replies", "Hindi clinic call: डॉक्टर ने कहा कि अपॉइंटमेंट कल सुबह 10 बजे है। User goal: confirm appointment. Never commit to payment or disclose personal data.", Suggestions),
        ("translate", "Tamil caller asked: உங்கள் கணக்கு நிலுவைத் தொகை ₹5,240.50. Translate to Hindi, preserving amount exactly.", Translation),
        ("apply_tone_combined", "Reply in Tamil politely: I will check and call you back. Preserve facts. Return rewritten text and optional one appropriate Timbre v3 tag.", ToneRewrite),
        ("summarize_call", "Kannada delivery call: package at gate, caller asked to wait five minutes. Summarize outcomes and open items in Kannada.", Summary),
        ("suggest_replies_tamil", "Tamil-English bank call: due amount is ₹12,450; user asks what options exist. Do not commit to payment or share OTP/PIN.", Suggestions),
        ("summarize_hindi", "Hindi call: clinic appointment Friday 11:30, call back number 9876543210. Summarize in Hindi.", Summary),
    ]
    for task, prompt, schema in tests:
        started = time.perf_counter(); status = "ok"
        try:
            response = client.models.generate_content(model=model, contents=prompt, config=types.GenerateContentConfig(response_mime_type="application/json", response_schema=schema))
            value = schema.model_validate_json(response.text or "")
            output = value.model_dump()
            usage = getattr(response, "usage_metadata", None)
            usage_data = {"prompt_tokens": getattr(usage, "prompt_token_count", None), "output_tokens": getattr(usage, "candidates_token_count", None)}
        except Exception as exc:
            status = type(exc).__name__; output = str(exc)[:500]; usage_data = {}
            usage_data["http_status"] = getattr(exc, "status_code", None) or getattr(exc, "code", None)
        print(json.dumps({"task": task, "model": model, "status": status, "latency_s": round(time.perf_counter()-started, 3), "json_valid": status == "ok", "usage": usage_data, "output": output}, ensure_ascii=False))


def main() -> None:
    load_dotenv(ROOT / ".env")
    gnani_key, gemini_key = require_keys()
    clip = Path(os.getenv("SMOKE_AUDIO_FILE", "")) if env("SMOKE_AUDIO_FILE") else speech_fixture(gnani_key)
    if not clip.exists(): raise SystemExit("SMOKE_AUDIO_FILE does not exist")
    print(f"Audio fixture: {clip}")
    stt_rest(gnani_key, clip)
    asyncio.run(stt_stream(gnani_key, clip))
    tts(gnani_key)
    llm_bakeoff(gemini_key)


if __name__ == "__main__":
    main()
