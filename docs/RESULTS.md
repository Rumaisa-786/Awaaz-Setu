# Awaaz Setu Evaluation Results

Run timestamp (UTC): 2026-11-15T08:43:35+00:00
Mode: **LIVE PROVIDER RUN**

## Provider and end-to-end latency

| Component | p50 | p95 | Samples / notes |
|---|---:|---:|---|
| Prisma WSS handshake | 362.1 ms | 454.1 ms | 24 streams |
| Prisma final segment server latency | 128.0 ms | 150.0 ms | 23 provider latency values |
| Prisma last frame to final transcript (wall) | 1828.1 ms | 2336.5 ms | 23 paced clean/noisy streams |
| Timbre SSE first audio byte | 2797.9 ms | 6610.4 ms | 6 utterances |
| Timbre WS first audio byte | 4253.7 ms | 4343.9 ms | 3 requests |
| Gemini combined translate + tone JSON | 1064.0 ms | 2632.9 ms | 5 strict JSON calls |

## STT WER / CER: context card A/B

| Audio condition | Keyterms | Utterances | WER | CER | Errors |
|---|---:|---:|---:|---:|---:|
| clean_16k | off | 6 | 0.630 | 0.354 | 0 |
| clean_16k | on | 6 | 0.479 | 0.318 | 0 |
| degraded_8k | off | 5 | 0.505 | 0.316 | 1 |
| degraded_8k | on | 6 | 0.456 | 0.276 | 0 |

## Entity and sensitive-request extraction

| Metric | Precision | Recall | TP | FP | FN | Cases |
|---|---:|---:|---:|---:|---:|---:|
| Entity spans (exact type/value) | 0.900 | 0.900 | 9 | 1 | 1 | 15 |
| OTP/PIN/CVV/password request | 1.000 | 1.000 | 5 | 0 | 0 | 15 |

## Method and limitations

- Timbre generated 6 synthetic multilingual speech clips. No live microphone clips were used.
- Clean audio was converted from generated WAV to 16 kHz mono. Degraded audio was resampled to 8 kHz, band-pass filtered from approximately 300–3400 Hz, and mixed with deterministic white noise at 10 dB SNR.
- Context A/B compares only each utterance's listed domain keyterms. The degraded 8 kHz no-keyterms cell has one stream failure; the other 23 Prisma streams returned final transcripts.
- WER/CER are computed against the exact scripted text spoken by synthetic Timbre voices. Accent, TTS pronunciation, and the small sample size limit generalisation to human callers.
- One Prisma connection closed during audio send after its handshake. No transcript output or credentials were written to the report.
- Entity/risk metrics test deterministic extraction against 15 hand-labelled utterances; they do not measure ASR entity capture.
- Gemini latency covers five combined translate-and-tone JSON calls. API rate and quality are specific to this run and sample set.

These are live provider measurements from the run above. No WER/CER value is inferred for a failed stream.
