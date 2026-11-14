# Gnani M0 Smoke Test Findings

> No live smoke run has been recorded yet. The sections below are a template, not verified measurements; implementation defaults currently follow the checked-in Gnani API documentation and should be treated as provisional until a human-run smoke test fills this page.

Run date:
Operator:
Client/runtime versions:
Base URL (never include credentials):

## Prisma v3 REST

| Case | Input / parameters | HTTP status | Transcript / detected language | Latency | Notes |
|---|---|---:|---|---:|---|
| indic-auto, verbatim | | | | | |
| Hindi, transcribe | | | | | |
| Tamil / Kannada | | | | | |

## Prisma v3 Realtime WSS

| Probe | Result | Evidence / request ID |
|---|---|---|
| 1,024-byte frames at 16 kHz / 32 ms cadence | | |
| 1,024-byte frames at 8 kHz / 64 ms cadence | | |
| `x-model: prisma-v3.0` required | | |
| `x-format: transcribe` number normalization | | |
| `x-partials` behavior | | |
| `x-keyterms` accepted/effect | | |
| `x-bias-list` + `x-bias-score` accepted/effect | | |
| Errors, rate and concurrency behavior | | |

## Timbre v3.0 TTS

| Mode / voice / language | Status | Content-Type and actual audio format | Sample rate | First-byte latency | Notes |
|---|---:|---|---:|---:|---|
| REST | | | | | |
| SSE | | | | | |
| WebSocket | | | | | |

Audition WAVs are written to `tmp/tts-auditions/`. Record listening notes for all 13 tags (`<coughs>`, `<excited>`, `<exhales>`, `<giggle>`, `<laugh>`, `<pauses>`, `<shouting>`, `<sigh>`, `<slow>`, `<sniffles>`, `<whispers>`, `<yawns>`, `<clears throat>`) and selected voices. Note that tags count toward billable characters.

## Gemini bake-off

| Task | Language pair / scenario | Latency | JSON/schema valid | 429 / transient retries | Quality notes |
|---|---|---:|---|---|---|
| suggest_replies | Hindi clinic | | | | |
| translate | Tamil caller → Hindi user | | | | |
| apply_tone (combined) | Hindi polite reply → Tamil | | | | |
| summarize_call | Kannada delivery | | | | |

Record model chosen for `LLM_MODEL`, with rationale and remaining limitations:

## Decisions

* Preferred streaming TTS method and REST fallback:
* Preferred Prisma context hint field based on matched A/B recordings:
* Confirmed realtime header names and defaults:
* Selected v3.0 voice/tone defaults:
