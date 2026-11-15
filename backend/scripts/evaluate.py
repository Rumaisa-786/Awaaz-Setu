from __future__ import annotations

import argparse
import asyncio
import base64
import json
import math
import random
import re
import statistics
import struct
import sys
import time
import wave
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import websockets

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(ROOT))

from app.calls.tones import Tone, sanitize_tts_text  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.entities import detect_security_risk, extract_entities  # noqa: E402
from app.gnani.tts import _strip_repeated_wav_header  # noqa: E402
from app.llm.tasks import relay_reply  # noqa: E402


@dataclass(frozen=True)
class Sample:
    text: str
    language: str
    keyterms: tuple[str, ...] = ()


SAMPLES = [
    Sample("डॉ. शर्मा ने कल सुबह 10:00 AM पर मिलने को कहा।", "hi-IN", ("Dr. Sharma",)),
    Sample("मुझे ₹5,00,000 की रसीद चाहिए।", "hi-IN", ("₹5,00,000",)),
    Sample("Awaaz Setu का appointment Indiranagar clinic में है।", "hi-en", ("Awaaz Setu", "Indiranagar")),
    Sample("क्या delivery आज शाम 6:30 बजे आएगी?", "hi-IN"),
    Sample("मेरा phone number 9876543210 है।", "hi-IN"),
    Sample("Please confirm the bank due amount is ₹450.", "en-IN"),
    Sample("Please do not ask me to share an OTP on this call.", "en-IN"),
    Sample("அப்பாயின்மென்ட் நாளை காலை 10:00 மணிக்கு இருக்கிறது.", "ta-IN"),
    Sample("டாக்டர் சர்மா, இந்த முகவரியை உறுதிப்படுத்துங்கள்.", "ta-IN", ("Dr. Sharma",)),
    Sample("ನಾಳೆ ಬೆಳಿಗ್ಗೆ 9:30ಕ್ಕೆ ಆಸ್ಪತ್ರೆಗೆ ಬರಬೇಕು.", "kn-IN"),
    Sample("ಹಣ ₹5,000 ಆಗಿದೆ, ದಯವಿಟ್ಟು ದೃಢೀಕರಿಸಿ.", "kn-IN"),
    Sample("డెలివరీ ఆర్డర్ AB-12345 ఈరోజు వస్తుంది.", "te-IN"),
    Sample("કૃપા કરીને બેંકનો સમય 4:00 PM નોંધો.", "gu-IN"),
    Sample("कृपया अपना PIN या CVV फोन पर न बताएं।", "hi-IN"),
    Sample("The clinic is at Indiranagar, call 9876543210 if late.", "en-IN", ("Indiranagar",)),
]

ENTITY_CASES = [
    ("खाता राशि ₹5,00,000 है।", {("amount", "₹5,00,000")}, False),
    ("कैश ऑन डिलीवरी ₹450 है।", {("amount", "₹450")}, False),
    ("आइए 10:00 AM पर।", {("time", "10:00 AM")}, False),
    ("तारीख 14/11/2026 है।", {("date", "14/11/2026")}, False),
    ("मुझे 9876543210 पर कॉल करें।", {("phone", "9876543210")}, False),
    ("Please share your OTP now.", set(), True),
    ("अपना PIN बताइए।", set(), True),
    ("Your CVV is needed for verification.", set(), True),
    ("Booking reference AB-1234 confirmed.", {("reference_id", "AB-1234")}, False),
    ("The appointment is at 18:45.", {("time", "18:45")}, False),
    ("₹2,50,000 will be due on 05-12-2026.", {("amount", "₹2,50,000"), ("date", "05-12-2026")}, False),
    ("ನಿಮ್ಮ password ಹೇಳಿ.", set(), True),
    ("Phone 9123456789 is registered.", {("phone", "9123456789")}, False),
    ("The meeting is tomorrow.", set(), False),
    ("Do not share a card number or one-time password.", set(), True),
]


def _tokens(text: str) -> list[str]:
    return re.findall(r"\w+|[^\w\s]", text.casefold())


def _distance(left: list[Any], right: list[Any]) -> int:
    row = list(range(len(right) + 1))
    for i, a in enumerate(left, 1):
        current = [i]
        for j, b in enumerate(right, 1):
            current.append(min(current[-1] + 1, row[j] + 1, row[j - 1] + (a != b)))
        row = current
    return row[-1]


def wer_cer(reference: str, hypothesis: str) -> tuple[float, float]:
    ref_words, hyp_words = _tokens(reference), _tokens(hypothesis)
    ref_chars, hyp_chars = list("".join(ref_words)), list("".join(hyp_words))
    return (_distance(ref_words, hyp_words) / max(1, len(ref_words)), _distance(ref_chars, hyp_chars) / max(1, len(ref_chars)))


def percentiles(values: list[float]) -> tuple[float | None, float | None]:
    if not values:
        return None, None
    ordered = sorted(values)
    def at(q: float) -> float:
        return ordered[min(len(ordered) - 1, max(0, math.ceil(q * len(ordered)) - 1))]
    return at(.5), at(.95)


def _metric_rows() -> dict[str, Any]:
    tp = fp = fn = risk_tp = risk_fp = risk_fn = 0
    for text, expected, risk_expected in ENTITY_CASES:
        actual = {(entity.type, entity.value) for entity in extract_entities(text)}
        tp += len(actual & expected); fp += len(actual - expected); fn += len(expected - actual)
        risk_actual = detect_security_risk(text)
        risk_tp += int(risk_actual and risk_expected); risk_fp += int(risk_actual and not risk_expected); risk_fn += int(risk_expected and not risk_actual)
    return {
        "entity": {"precision": tp / max(1, tp + fp), "recall": tp / max(1, tp + fn), "tp": tp, "fp": fp, "fn": fn, "cases": len(ENTITY_CASES)},
        "risk": {"precision": risk_tp / max(1, risk_tp + risk_fp), "recall": risk_tp / max(1, risk_tp + risk_fn), "tp": risk_tp, "fp": risk_fp, "fn": risk_fn, "cases": len(ENTITY_CASES)},
    }


def _wav_bytes(samples: list[int], sample_rate: int) -> bytes:
    import io
    target = io.BytesIO()
    with wave.open(target, "wb") as output:
        output.setnchannels(1); output.setsampwidth(2); output.setframerate(sample_rate)
        output.writeframes(struct.pack("<" + "h" * len(samples), *samples))
    return target.getvalue()


def _mock_carrier_audio(sample_rate: int = 16000, seconds: float = .7) -> list[int]:
    # Tone sweep is intentionally non-speech; offline mode exercises file/degradation plumbing only.
    count = int(sample_rate * seconds)
    return [int(7000 * math.sin(2 * math.pi * (170 + (i / sample_rate) * 100) * i / sample_rate)) for i in range(count)]


def _degrade_to_8k(samples16k: list[int], seed: int = 7, snr_db: float = 10) -> list[int]:
    down = [(samples16k[i] + samples16k[min(i + 1, len(samples16k) - 1)]) // 2 for i in range(0, len(samples16k), 2)]
    fs = 8000
    hp_a = math.exp(-2 * math.pi * 300 / fs); lp_a = 1 - math.exp(-2 * math.pi * 3400 / fs)
    hp_out: list[float] = []; prev_in = prev_hp = 0.0
    for value in down:
        cur = hp_a * (prev_hp + value - prev_in); hp_out.append(cur); prev_in, prev_hp = value, cur
    band: list[float] = []; prev_lp = 0.0
    for value in hp_out:
        prev_lp += lp_a * (value - prev_lp); band.append(prev_lp)
    rms = math.sqrt(sum(v * v for v in band) / max(1, len(band)))
    sigma = rms / (10 ** (snr_db / 20)); randomizer = random.Random(seed)
    return [max(-32768, min(32767, int(value + randomizer.gauss(0, sigma)))) for value in band]


def _write_mock_audio() -> int:
    output = ROOT / "tmp" / "eval"; output.mkdir(parents=True, exist_ok=True)
    written = 0
    for index, sample in enumerate(SAMPLES, 1):
        clean = _mock_carrier_audio()
        for label, data, rate in (("clean_16k", clean, 16000), ("degraded_8k", _degrade_to_8k(clean, index), 8000)):
            (output / f"mock_{index:02d}_{label}.wav").write_bytes(_wav_bytes(data, rate)); written += 1
    return written


def _markdown_report(result: dict[str, Any]) -> str:
    stamp = result["run_utc"]
    lines = ["# Awaaz Setu Evaluation Results", "", f"Run timestamp (UTC): {stamp}", f"Mode: **{result['mode']}**", "", "## Provider and end-to-end latency", "", "| Component | p50 | p95 | Samples / notes |", "|---|---:|---:|---|"]
    for item in result["latency"]:
        lines.append(f"| {item['component']} | {item['p50']} | {item['p95']} | {item['notes']} |")
    lines.extend(["", "## STT WER / CER: context card A/B", "", "| Audio condition | Keyterms | Utterances | WER | CER | Errors |", "|---|---:|---:|---:|---:|---:|"])
    for item in result["accuracy"]:
        lines.append(f"| {item['condition']} | {item['keyterms']} | {item['n']} | {item['wer']} | {item['cer']} | {item.get('errors', 0)} |")
    lines.extend(["", "## Entity and sensitive-request extraction", "", "| Metric | Precision | Recall | TP | FP | FN | Cases |", "|---|---:|---:|---:|---:|---:|---:|"])
    for name, metric in (("Entity spans (exact type/value)", result["extraction"]["entity"]), ("OTP/PIN/CVV/password request", result["extraction"]["risk"])):
        lines.append(f"| {name} | {metric['precision']:.3f} | {metric['recall']:.3f} | {metric['tp']} | {metric['fp']} | {metric['fn']} | {metric['cases']} |")
    lines.extend(["", "## Method and limitations", ""])
    lines.extend(f"- {note}" for note in result["notes"])
    lines.extend(["", "Accuracy figures are reported only for runs that actually invoke Prisma on speech audio. No live API results are inferred from mock-mode checks.", ""])
    return "\n".join(lines)


def run_mock() -> dict[str, Any]:
    files = _write_mock_audio()
    extraction = _metric_rows()
    return {
        "run_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "mode": "MOCK / OFFLINE",
        "latency": [
            {"component": "Prisma WSS handshake + final segment", "p50": "Not measured", "p95": "Not measured", "notes": "No provider request in mock mode"},
            {"component": "Timbre SSE / WS first audio byte", "p50": "Not measured", "p95": "Not measured", "notes": "No provider request in mock mode"},
            {"component": "Gemini combined translate + tone JSON", "p50": "Not measured", "p95": "Not measured", "notes": "Mock JSON schema exercised; provider latency is not measured"},
        ],
        "accuracy": [{"condition": c, "keyterms": k, "n": "—", "wer": "Not measured", "cer": "Not measured"} for c in ("Clean synthetic 16 kHz tone (not speech)", "Degraded 8 kHz synthetic tone (not speech)") for k in ("off", "on")],
        "extraction": extraction,
        "notes": [f"Offline validation only. Wrote {files} synthetic tone WAV files under tmp/eval/; they are not speech samples and are not sent to any service.", "Entity and request-warning metrics are measured against the hand-authored 15-case local fixture in this run; they are not ASR or production metrics.", "WER/CER, provider latencies and language quality remain unmeasured in mock mode.", "The live run uses .env credentials only when MOCK_MODE=false and must be started explicitly by the operator.", "Synthetic Timbre speech is cleaner than real callers; this harness currently does not ingest live microphone recordings or carrier-call audio."],
    }


def _wav_pcm(data: bytes) -> tuple[list[int], int]:
    import io
    with wave.open(io.BytesIO(data), "rb") as source:
        if source.getnchannels() != 1 or source.getsampwidth() != 2:
            raise ValueError("Evaluation requires mono 16-bit linear PCM WAV")
        rate = source.getframerate(); raw = source.readframes(source.getnframes())
    return list(struct.unpack("<" + "h" * (len(raw) // 2), raw)), rate


def _resample(samples: list[int], source_rate: int, target_rate: int) -> list[int]:
    if source_rate == target_rate: return samples
    length = int(len(samples) * target_rate / source_rate)
    return [samples[min(len(samples)-1, int(i * source_rate / target_rate))] for i in range(length)]


async def _tts_sse(settings: Any, sample: Sample) -> tuple[bytes, float]:
    payload = {"text": sample.text, "voice": "Shivani", "model": "timbre-v3.0", "language": sample.language, "audio_config": {"sample_rate": 24000, "encoding": "linear_pcm", "container": "wav"}}
    started = time.perf_counter(); first: float | None = None; chunks: list[bytes] = []
    async with httpx.AsyncClient(timeout=httpx.Timeout(45, connect=10)) as client:
        async with client.stream("POST", settings.gnani_base_url.rstrip("/") + "/api/v1/tts/sse", headers={"X-API-Key-ID": settings.gnani_api_key.get_secret_value()}, json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.startswith("data:"): continue
                event = json.loads(line[5:].strip())
                if event.get("audio"):
                    if first is None: first = (time.perf_counter() - started) * 1000
                    raw_b = base64.b64decode(event["audio"])
                    chunks.append(_strip_repeated_wav_header(raw_b, first_chunk=not chunks))
                if event.get("is_final"): break
    if first is None or not chunks: raise RuntimeError("Timbre SSE returned no audio chunk")
    return b"".join(chunks), first


async def _tts_ws_first_byte(settings: Any) -> float:
    payload = {"text": "नमस्ते, मैं आपकी सहायता के लिए यहाँ हूँ।", "voice": "Shivani", "model": "timbre-v3.0", "language": "hi-IN", "audio_config": {"sample_rate": 24000, "encoding": "linear_pcm", "container": "wav"}}
    endpoint = settings.gnani_base_url.rstrip("/").replace("https://", "wss://").replace("http://", "ws://") + "/api/v1/tts"
    start = time.perf_counter(); first: float | None = None
    async with websockets.connect(endpoint, additional_headers={"X-API-Key-ID": settings.gnani_api_key.get_secret_value(), "Content-Type": "application/json"}, open_timeout=10, close_timeout=2) as socket:
        await socket.send(json.dumps(payload, ensure_ascii=False))
        async with asyncio.timeout(15):
            async for raw in socket:
                if isinstance(raw, bytes):
                    if raw: first = (time.perf_counter() - start) * 1000; break
                event = json.loads(raw); data = event.get("data", event)
                if data.get("audio"):
                    first = (time.perf_counter() - start) * 1000; break
    if first is None: raise RuntimeError("Timbre WS produced no first audio chunk")
    return first


async def _stt_ws(settings: Any, pcm: list[int], sample_rate: int, language: str, keyterms: tuple[str, ...], diagnostics: dict[str, Any] | None = None) -> tuple[str, float, float | None, float]:
    endpoint = settings.gnani_base_url.rstrip("/").replace("https://", "wss://").replace("http://", "ws://") + "/stt/v3/stream"
    headers = {"x-api-key-id": settings.gnani_api_key.get_secret_value(), "language_code": "indic-auto", "x-sample-rate": str(sample_rate), "x-format": "transcribe", "x-partials": "true"}
    headers["x-model"] = "prisma-v3.0"
    if keyterms: headers["x-keyterms"] = json.dumps(list(keyterms), ensure_ascii=True)
    start = time.perf_counter(); final_start: float | None = None; server_latency: float | None = None; text = ""
    if diagnostics is not None: diagnostics.update(stage="connect", events=[])
    async with websockets.connect(endpoint, additional_headers=headers, open_timeout=15, close_timeout=3, max_size=4_000_000) as socket:
        handshake = (time.perf_counter() - start) * 1000
        if diagnostics is not None: diagnostics.update(stage="send_audio", handshake_ms=handshake)
        # Prisma may stay silent until it receives its first PCM frame. Do not
        # wait for a greeting here: that would deadlock the audio/VAD exchange.
        pace = 0.032 if sample_rate == 16000 else 0.064
        for offset in range(0, len(pcm), 512):
            frame = pcm[offset:offset + 512]
            if len(frame) < 512: frame += [0] * (512 - len(frame))
            await socket.send(struct.pack("<512h", *frame))
            await asyncio.sleep(pace)
        final_start = time.perf_counter()
        if diagnostics is not None: diagnostics["stage"] = "await_final_transcript"
        # Prisma commits utterances through VAD; this endpoint has no commit message.
        for _ in range(16):
            await socket.send(bytes(1024))
            await asyncio.sleep(pace)
        parts: list[str] = []
        speech_ended = False
        async with asyncio.timeout(15):
            async for raw in socket:
                if not isinstance(raw, str): continue
                event = json.loads(raw)
                if diagnostics is not None: diagnostics["events"].append(str(event.get("type", "unknown")))
                if event.get("type") == "error": raise RuntimeError("Prisma returned a stream error")
                if event.get("type") == "speech_end":
                    speech_ended = True
                if event.get("type") in {"transcript", "final_transcript"}:
                    segment = str(event.get("text", "")).strip()
                    if segment: parts.append(segment)
                    try: server_latency = float(event.get("latency", 0))
                    except (TypeError, ValueError): server_latency = None
                    # Observed v3 sends the committed transcript after speech_end.
                    if speech_ended:
                        break
                if speech_ended and parts:
                    break
        text = " ".join(p for p in parts if p)
    wall = (time.perf_counter() - (final_start or time.perf_counter())) * 1000
    if not text: raise RuntimeError("Prisma stream ended without a final transcript")
    return text, handshake, server_latency, wall


async def run_live(samples_count: int) -> dict[str, Any]:
    settings = get_settings()
    if settings.mock_mode:
        raise SystemExit("Live eval is disabled while MOCK_MODE=true. Set MOCK_MODE=false in .env; this script never prints credentials.")
    if not settings.gnani_api_key.get_secret_value() or not settings.gemini_api_key.get_secret_value():
        raise SystemExit("Live eval requires GNANI_API_KEY and GEMINI_API_KEY in .env.")
    samples = SAMPLES[:max(1, min(len(SAMPLES), samples_count))]
    outdir = ROOT / "tmp" / "eval"; outdir.mkdir(parents=True, exist_ok=True)
    handshake_times: list[float] = []; stt_times: list[float] = []; stt_wall_times: list[float] = []; tts_sse_times: list[float] = []; tts_ws_times: list[float] = []; llm_times: list[float] = []
    audio_sets: list[tuple[Sample, list[int], list[int]]] = []
    accuracy: dict[tuple[str, str], dict[str, float]] = {}
    failure_counts: dict[str, int] = {}
    for index, sample in enumerate(samples, 1):
        wav_data, sse_first = await _tts_sse(settings, sample); tts_sse_times.append(sse_first)
        (outdir / f"live_{index:02d}_{sample.language}.wav").write_bytes(wav_data)
        pcm24, rate = _wav_pcm(wav_data); clean16 = _resample(pcm24, rate, 16000); noisy8 = _degrade_to_8k(clean16, index)
        audio_sets.append((sample, clean16, noisy8))
    for _ in range(3):
        try: tts_ws_times.append(await _tts_ws_first_byte(settings))
        except Exception: break
    for sample, clean16, noisy8 in audio_sets:
        for condition, pcm, rate in (("clean_16k", clean16, 16000), ("degraded_8k", noisy8, 8000)):
            for use_terms in (False, True):
                terms = sample.keyterms if use_terms else ()
                try:
                    diagnostic: dict[str, Any] = {}
                    hypothesis, handshake, server_latency, wall_latency = await _stt_ws(settings, pcm, rate, sample.language, terms, diagnostic)
                    handshake_times.append(handshake); stt_wall_times.append(wall_latency)
                    if server_latency is not None: stt_times.append(server_latency)
                    wer, cer = wer_cer(sample.text, hypothesis)
                    key = (condition, "on" if use_terms else "off")
                    bucket = accuracy.setdefault(key, {"wer": 0.0, "cer": 0.0, "n": 0, "errors": 0})
                    bucket["wer"] += wer; bucket["cer"] += cer; bucket["n"] += 1
                except Exception as exc:
                    if diagnostic.get("handshake_ms") is not None:
                        handshake_times.append(float(diagnostic["handshake_ms"]))
                    failure = f"{type(exc).__name__} during {diagnostic.get('stage', 'unknown')}"
                    failure_counts[failure] = failure_counts.get(failure, 0) + 1
                    # Avoid exception strings because libraries can include request headers in errors.
                    accuracy.setdefault((condition, "on" if use_terms else "off"), {"wer": 0.0, "cer": 0.0, "n": 0, "errors": 0})["errors"] += 1
                    events_seen = ",".join(diagnostic.get("events", [])) or "none"
                    print(f"STT sample skipped ({type(exc).__name__}; stage={diagnostic.get('stage', 'unknown')}; events={events_seen})")
    for sample in samples[:min(5, len(samples))]:
        start = time.perf_counter(); result = await relay_reply(sample.text, sample.language, "ta-IN" if sample.language != "ta-IN" else "hi-IN", Tone.POLITE); llm_times.append((time.perf_counter() - start) * 1000)
        if result.uncertainty: print("Gemini combined translate+tone returned fallback for one sample")
    accuracy_rows = []
    for (condition, terms), values in sorted(accuracy.items()):
        n = values["n"]
        accuracy_rows.append({"condition": condition, "keyterms": terms, "n": n, "wer": f"{values['wer']/n:.3f}" if n else "No valid transcript", "cer": f"{values['cer']/n:.3f}" if n else "No valid transcript", "errors": values.get("errors", 0)})
    extraction = _metric_rows()
    def row(name: str, values: list[float], notes: str) -> dict[str, str]:
        p50, p95 = percentiles(values)
        return {"component": name, "p50": f"{p50:.1f} ms" if p50 is not None else "No data", "p95": f"{p95:.1f} ms" if p95 is not None else "No data", "notes": notes}
    return {
        "run_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "mode": "LIVE PROVIDER RUN",
        "latency": [row("Prisma WSS handshake", handshake_times, f"{len(handshake_times)} streams"), row("Prisma final segment server latency", stt_times, f"{len(stt_times)} provider latency values"), row("Prisma last frame to final transcript (wall)", stt_wall_times, f"{len(stt_wall_times)} paced clean/noisy streams"), row("Timbre SSE first audio byte", tts_sse_times, f"{len(tts_sse_times)} utterances"), row("Timbre WS first audio byte", tts_ws_times, f"{len(tts_ws_times)} requests"), row("Gemini combined translate + tone JSON", llm_times, f"{len(llm_times)} strict JSON calls")],
        "accuracy": accuracy_rows, "extraction": extraction,
        "notes": [f"Timbre generated {len(samples)} synthetic multilingual speech clips; all generated audio is labelled synthetic. No live microphone clips were used.", "Clean audio was converted from the generated WAV to 16 kHz mono; degraded audio was resampled to 8 kHz, band-pass filtered from approximately 300–3400 Hz, and mixed with deterministic white noise at 10 dB SNR.", "Context A/B uses only each utterance's listed domain keyterms. A zero-result cell indicates provider failure/stream timeout, not a zero WER.", "WER/CER are computed against the exact scripted text spoken by synthetic Timbre voices. Accent, TTS pronunciation and small sample size limit their generalisation to human callers.", "Entity/risk metrics test deterministic extraction against 15 hand-labelled utterances; they do not measure ASR entity capture.", "No human microphone or carrier-call audio is in this evaluation. Prisma realtime sessions are capped at 15 minutes; LLM rate limits and provider failures can cause skipped samples."] + [f"Prisma stream failures: {failure} × {count}." for failure, count in sorted(failure_counts.items())],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Offline or paid API evaluation for Awaaz Setu")
    parser.add_argument("--mock", action="store_true", help="Run offline fixtures only; makes no API calls")
    parser.add_argument("--samples", type=int, default=len(SAMPLES), help="Number of scripted live speech samples (max 15)")
    args = parser.parse_args()
    ROOT.joinpath(".env")  # Settings reads the root env after cwd is set.
    import os
    os.chdir(ROOT)
    result = run_mock() if args.mock else asyncio.run(run_live(args.samples))
    report = _markdown_report(result)
    results_path = ROOT / "docs" / "RESULTS.md"; results_path.parent.mkdir(parents=True, exist_ok=True)
    results_path.write_text(report, encoding="utf-8")
    json_path = ROOT / "tmp" / "eval" / "latest.json"; json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {results_path.relative_to(ROOT)} ({result['mode']}). No API keys or transcript outputs were printed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
