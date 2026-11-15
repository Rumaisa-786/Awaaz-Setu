# Gnani M0 Smoke Test Findings

> **Provenance:** The numeric findings below were supplied by the project owner in the Milestone 7–9 task. They were not present in the prior checked-in template, and no raw logs, request IDs, run date, or operator details were provided. Treat them as owner-reported measurements pending attachment of original evidence; this agent did not rerun any paid/live smoke tests.

Run date: Not supplied
Operator: Project owner (name not supplied)
Client/runtime versions: Not supplied
Base URL (never include credentials): `https://api.vachana.ai`

## Prisma v3 REST

| Case | Input / parameters | HTTP status | Transcript / detected language | Latency | Notes |
|---|---|---:|---|---:|---|
| indic-auto, verbatim | Not supplied | Not supplied | Not supplied | Not supplied | Owner did not provide REST-specific result |
| Hindi, transcribe | Hindi number-normalization probe | Not supplied | `5,00,000` normalization reported | Not supplied | Owner-reported; raw request/response not attached |
| Tamil / Kannada | Not supplied | Not supplied | Not supplied | Not supplied | Owner did not provide language-specific REST result |

## Prisma v3 Realtime WSS

| Probe | Result | Evidence / request ID |
|---|---|---|
| 1,024-byte frames at 16 kHz / 32 ms cadence | 512 samples / 1,024 bytes at 16,000 Hz reported | Owner-reported; request IDs not supplied |
| 1,024-byte frames at 8 kHz / 64 ms cadence | Not supplied | Not supplied |
| `x-model: prisma-v3.0` required | Not supplied | Not supplied |
| `x-format: transcribe` number normalization | Indian number `5,00,000` normalization reported | Owner-reported; raw transcript not attached |
| `x-partials` behavior | `x-partials: true` with partials at approximately 450 ms intervals reported | Owner-reported; measurement method not supplied |
| Final segment latency | 37–58 ms reported | Owner-reported; sample count and latency source not supplied |
| `x-keyterms` accepted/effect | Not supplied | A/B result not supplied |
| `x-bias-list` + `x-bias-score` accepted/effect | Not supplied | A/B result not supplied |
| Errors, rate and concurrency behavior | Not supplied | Not supplied |

## Timbre v3.0 TTS

| Mode / voice / language | Status | Content-Type and actual audio format | Sample rate | First-byte latency | Notes |
|---|---:|---|---:|---:|---|
| REST | Reported working | Mono WAV / PCM | 24,000 Hz | 3.2–4.2 s | Owner-reported range; exact voice/sample count not supplied |
| SSE | Reported working | Mono WAV / PCM | 24,000 Hz | 0.602 s | Owner-reported; exact voice/language not supplied |
| WebSocket | Reported working | Mono WAV / PCM | 24,000 Hz | 0.671 s | Owner-reported; exact voice/language not supplied |

Audition WAVs are written to `tmp/tts-auditions/`. The owner reported that the implementation uses strict sanitization against the 13-tag allow-list. Listening notes for each tag and selected voice were not supplied. Tags: `<coughs>`, `<excited>`, `<exhales>`, `<giggle>`, `<laugh>`, `<pauses>`, `<shouting>`, `<sigh>`, `<slow>`, `<sniffles>`, `<whispers>`, `<yawns>`, `<clears throat>`.

## Gemini bake-off

| Task | Language pair / scenario | Latency | JSON/schema valid | 429 / transient retries | Quality notes |
|---|---|---:|---|---|---|
| suggest_replies | Hindi clinic | 0.99–1.84 s reported across tasks | Strict JSON reported | Not supplied | Per-task breakdown not supplied |
| translate | Tamil caller → Hindi user | 0.99–1.84 s reported across tasks | Strict JSON reported | Not supplied | Per-task breakdown not supplied |
| apply_tone (combined) | Hindi polite reply → Tamil | 0.99–1.84 s reported across tasks | Strict JSON reported | Not supplied | Combined translate+tone call reported |
| summarize_call | Kannada delivery | 0.99–1.84 s reported across tasks | Strict JSON reported | Not supplied | Per-task breakdown not supplied |

Reported model: `gemini-3.5-flash-lite`. Rationale, sample count, token counts, quality notes, and retry totals were not supplied.

## Decisions and open evidence

* Preferred streaming TTS method: SSE (reported first-byte 0.602 s vs WS 0.671 s); REST fallback (reported 3.2–4.2 s).
* Preferred Prisma context hint field based on matched A/B recordings: **Not established in supplied evidence**. Keep `x-keyterms` behavior provisional until paired results are recorded.
* Confirmed realtime header names and defaults: 16 kHz / 1,024-byte / 512-sample frame values reported; required-model/header A/B outcomes not supplied.
* Selected v3.0 voice/tone defaults: Not supplied; current implementation defaults are provisional.
* Attach raw logs, request IDs, run date, sample sizes, voice/language combinations, and context A/B results here to make these owner-reported figures independently auditable.
