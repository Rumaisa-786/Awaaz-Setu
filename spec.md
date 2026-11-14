# Awaaz Setu — Product & Build Spec

> Read `AGENTS.md` first. Build **one milestone at a time** (§14). Do not start a milestone until asked. Where this spec and `docs/gnani/` disagree on API details, the smoke-test results in `docs/gnani/FINDINGS.md` win.

---

## 1. Summary

**Awaaz Setu** ("Voice Bridge") lets a deaf or hard-of-hearing person make and take phone-style calls in Indian languages. It acts as the user's voice and ears:

- **Ears:** the caller's speech is transcribed live (Gnani **Prisma v3.0**) and shown as captions, with amounts, times and phone numbers pulled out into large confirmation cards.
- **Voice:** the user replies by **tapping a suggested reply, typing, or speaking**. Replies are spoken to the caller by Gnani **Timbre v3.0**, in the chosen language and **tone** (warm, polite, urgent, apologetic) using Timbre v3.0 audio tags and voice choice.
- **Cross-language:** the user can talk to someone who speaks a different Indian language. The caller's language is auto-detected; an LLM translates both ways and both original and translated text are shown.
- The caller hears an ordinary call and needs no app. In this build the caller joins by web link (§4); telephony is a later swap-in.

This is a **prototype for the Gnani "Great Indian AI Internship Challenge"**, built to be demoed in a short video, evaluated with real latency/accuracy measurements, and structured so it can later become a Play Store app.

### Honest positioning (use in README/UI copy; never overclaim)
The core idea of a text/voice phone relay already exists (e.g. Google's Live Relay). Awaaz Setu's contribution is: Indian-language and code-mixed support on phone-quality audio, **tone control**, **cross-language relay**, three input modes, and **measured** latency/accuracy. It is not a medical, emergency, or legal service.

---

## 2. Users and scenarios

| Persona | Needs |
|---|---|
| **Primary user** — deaf / hard of hearing, cannot or prefers not to use phone audio | Read the caller, reply fast, sound the way they mean to |
| **Speaking user** — hard of hearing but can speak | Speak replies directly (fast), read captions of the caller |
| **Callee** — hears a normal call | No app, a clear intro, natural-sounding voice |

Demo scenarios (scripted content is labelled "Demo scenario" in the UI):
1. **Clinic** — book an appointment (names, time, phone number confirmation).
2. **Bank** — check a due amount (₹ amounts, account terms).
3. **Delivery / Gate mode** — an unknown caller says "I'm at your gate"; auto-answer, one-tap replies.
4. **Cross-language** — user types Hindi/English, callee speaks Tamil (or another pair).

---

## 3. Scope

**In:** everything in §7.
**Out (do not build; list on a roadmap slide only):**
- Camera / sign-language recognition.
- Real PSTN/SIP phone numbers (design the `CalleeTransport` seam so it can be added).
- Call recording, voice cloning, autopilot (AI conducting a call alone), emergency calling.
- Any claim of support for Indian languages outside Gnani's 10.

---

## 4. Architecture

```
 ┌────────────── User device (PWA) ──────────────┐        ┌──── Callee device (browser) ────┐
 │ Live call UI                                    │        │ /join/:code  (consent, mic,     │
 │  mic ─(16 kHz PCM s16le)─┐   ▲ captions/events  │        │  speaker, optional captions)    │
 └───────────────────────────┼───┼─────────────────┘        └─────────┬──────────▲───────────┘
                    WS /ws/call/user   │                         WS /ws/call/callee
                             ▼   │                                     │ caller mic PCM   │ TTS / direct audio
 ┌────────────────────────────────────────────── FastAPI ───────────────────────────────────┴───────┐
 │ CallSession (one per call; owns state, limits, timers, reconnects)                                │
 │  ├─ CalleeTransport  (WebLinkTransport now · TelephonyTransport later)                            │
 │  ├─ STT proxy  ──► wss://api.vachana.ai/stt/v3/stream   (callee audio → captions)                 │
 │  ├─ STT proxy #2 ► (user mic, only in "speak & transform" mode)                                   │
 │  ├─ TTS client ──► Gnani Timbre v3.0 (text → audio → callee)                                      │
 │  ├─ LLM provider (suggestions · translation · tone/register rewrite · summary)                    │
 │  └─ Entity extractor (amounts, times, dates, phone numbers, PINs) — deterministic, unit-tested    │
 └───────────────────────────────────────────────────────────────────────────────────────────────────┘
```

**Why the callee joins by web link:** it gives two cleanly separated audio channels (no echo between caller and user), works on any phone browser, shows multi-user isolation, and avoids telephony setup. The `CalleeTransport` interface (`connect`, `send_audio(pcm)`, `on_audio(pcm)`, `close`) lets a SIP/Twilio/LiveKit transport replace it later.

**Session model:** every call has `call_id`, `owner_user_id`, `join_code` (short, single-use, expires), `state` (`setup → ringing → live → ended`), languages, mode, tone, voice, context card, counters for cost guards. A user can only access their own calls (enforced server-side).

**Audio:** browser captures with an `AudioWorklet`, resamples to **16 kHz mono PCM s16le**, and sends **exactly 1,024-byte frames (512 samples) at real-time cadence** (32 ms). The API forwards frames unchanged to Gnani. Constants live in one module with tests. Callee playback uses Web Audio; handle the sample rate/format Timbre actually returns (see FINDINGS).

---

## 5. Gnani integration rules

Verified from the docs on 14 Nov 2026 (re-verify in Milestone 0):

- Base URL `https://api.vachana.ai`; auth header `X-API-Key-ID` (REST) / `x-api-key-id` (WS).
- **Prisma v3.0:** `model=prisma-v3.0`. Languages: `bn-IN en-IN gu-IN hi-IN kn-IN ml-IN mr-IN pa-IN ta-IN te-IN`, plus `indic-auto` (auto-detect). Language codes are hints, not locks; send 1–4 codes. REST `POST /stt/v3` (multipart `audio_file`, ≤30 s). **Realtime** `WSS /stt/v3/stream`: headers `x-api-key-id`, `lang_code`, `x-sample-rate` (8000/16000/44100/48000), `x-format` (`verbatim|transcribe|codemix|transliterate`), `x-model: prisma-v3.0`, VAD headers (`x-vad-threshold`, `x-min-silence-ms`, `x-min-speech-ms`, `x-min-segment-ms`, `x-max-speech-s`). Server messages: `connected`, `processing` (end of speech detected), `transcript` (`text`, `segment_id`, `segment_index`, `audio_duration_ms`, `latency`), `error`, `settings_updated`. Transcripts arrive **per VAD segment** (after a silence timer), not token by token. Session cap **15 minutes**. Telephony VAD starting point: threshold 0.7, min-speech 200 ms, min-silence 400–600 ms.
- **`x-format: transcribe`** runs inverse text normalization: amounts → `₹5,00,000`, times, dates, phone numbers → digits. Use it for the caller stream so number cards are accurate. With `indic-auto` the default style is `verbatim`; set `transcribe` explicitly and verify.
- **Context hints:** the Prisma v3 page documents `keyterms` (REST field / `x-keyterms` header, up to 200 items; `topic`, `previous_text`, `speaker_names` are **not** available when streaming). The older Realtime page documents `x-bias-list` + `x-bias-score` (up to 100 single words). **These conflict — test both in M0.** The docs warn context can *reduce* accuracy; always A/B it (§12).
- **Not provided by Prisma:** translation, word timestamps, diarization (REST/Realtime). We use the LLM for translation; we only send the **caller's** audio to the caller STT stream, so diarization is unnecessary.
- **Timbre:** `model` values `timbre-v3.0` (13 voices, **every voice speaks all 10 languages**, supports audio tags) and `timbre-v2.5` (42 voices, one preferred language each). Voices are **not interchangeable** between models. v3.0 voices: Shivani, Lakshmi, Kalpana, Chetana, Vasudha, Riyaa, Tarika (female); Avinash, Shubham, Prakash, Devansh, Yashraj, Harshad (male). Request body shape: `{"text","voice","model","language"}` (`language` may be `auto`). **Audio tags (v3.0 only):** `<coughs> <excited> <exhales> <giggle> <laugh> <pauses> <shouting> <sigh> <slow> <sniffles> <whispers> <yawns> <clears throat>`; v2.5 strips them and rejects tag-only text. TTS offers REST, SSE streaming and Realtime WebSocket — use the lowest-latency one that works in M0 and keep REST as fallback.
- Rate/concurrency limits: read `docs/gnani/15-stt-limits.md` and TTS limits; enforce a per-user and global cap in `limits.py`.
- The Python SDK does not expose VAD tuning for STT; use a raw `websockets` client.

---

## 6. LLM usage

Provider-agnostic interface; default provider/model from `.env` (`LLM_PROVIDER`, `LLM_MODEL`; default Anthropic `claude-haiku-5-5`). Swapping providers must be a config change plus one provider file. A bake-off in M0 chooses the final default (§14).

Tasks (all return strict JSON validated with pydantic; one retry on invalid JSON; 3 s timeout; mock implementation for `MOCK_MODE`):

1. **`suggest_replies`** — input: last ~6 turns, user goal, context card, user language, tone. Output: ≤4 short suggested replies (≤12 words each) + whether a free-text answer is needed. **Latency budget: first suggestions visible ≤ 1.5 s after the caller's transcript lands.** Stream or show as soon as ready; never block captions.
2. **`translate`** — source/target language codes, text, register (`formal|neutral|casual`). Preserves numbers, names, and amounts exactly; flags uncertainty.
3. **`apply_tone`** — rewrites a reply into the right politeness/register for the target language (e.g. Hindi *aap* form) and, for v3.0, optionally inserts one allowed audio tag. Never changes facts, numbers, or names.
4. **`summarize_call`** — outcomes (appointment time, amount, instructions, phone numbers), open items, plain language, user's language.

**Safety rules for every prompt:**
- Suggestions must **never commit the user to money, consent, legal agreement, or sharing personal/financial data** without it being an explicit user-chosen reply. Never invent user facts (name, account number, address). Use only the context card.
- Never give medical, legal, or financial advice; it only helps the user say what they choose to say.
- If the caller asks for an OTP, PIN, CVV, or card number, add a visible **warning card** ("Don't share this on a call") and do not suggest replies that share it.
- Keep suggestions in the user's language; keep numbers as digits in text.

---

## 7. Features and acceptance criteria

**F1 — Live captions.** Caller speech appears as caption bubbles within the latency measured in M0 (target: ≤ ~1.2 s after the caller stops speaking on 8–16 kHz audio). A "Caller is speaking…" indicator appears from the first VAD activity or `processing` event. Captions show detected language chip. Text size user-adjustable (16–28 px).

**F2 — Typed and tapped replies.** Typed text or a tapped suggestion is spoken to the callee with Timbre v3.0. Callee audio starts ≤ ~1.5 s after send (measure; record in FINDINGS). The UI shows `Sending → Speaking → Delivered` states.

**F3 — Reply suggestions.** Up to 4 chips above the composer; tapping sends (with a 3-second "undo" window toggle in settings). Includes pinned quick phrases: *Please repeat · Please speak slowly · One moment · Thank you · I'm using an assistive service.*

**F4 — Number & entity cards.** Deterministic extractor finds ₹ amounts, times, dates, 10-digit phone numbers and 6-digit PINs in caller transcripts (both Latin and Devanagari digits and spoken forms Prisma may emit). A **confirmation card** pins above the composer with the value in very large digits and buttons **"Read it back"** (speaks it to the caller) and **"Correct it"**. Unit tests cover ≥ 30 cases including lakh/crore grouping.

**F5 — Tone.** Tone selector: *Neutral, Warm, Polite (formal), Urgent, Apologetic*. Each maps to {voice, LLM register rewrite, optional audio tag, pacing via SSML if supported}. Audition every tag/voice in M0 (`scripts/smoke/tag_audition`) and **record in FINDINGS which tags sound appropriate**; only ship tags that sound natural in a serious call (e.g. do not default to `<laugh>`). Tone can be set per call and per message.

**F6 — Context card.** Before a call: goal, user's name, up to 20 names/terms (doctor, clinic, medicines, bank terms). Terms are passed to Prisma as keyterms/bias (per M0 findings) and to the LLM. A toggle "Use context hints" exists so the A/B in §12 is reproducible.

**F7 — Input modes (switchable mid-call):**
- **Type / tap.**
- **Speak (direct):** user's own voice is relayed to the callee with no STT/TTS. Zero added processing delay. Use `getUserMedia` with echo cancellation.
- **Speak & transform:** user's mic → second Prisma stream → (optional translation/tone) → Timbre → callee. Show **what you said** and **what the caller heard**. Toggle **auto-send** vs **review before send**. Half-duplex gating: pause the user STT stream while the callee is speaking and while TTS plays. Headphone recommendation shown once.
  Latency of each mode is logged separately (§12).

**F8 — Cross-language.** User language and callee language are selectable from the 10 supported. Callee stream uses `indic-auto` (or the expected language list) and the UI shows the detected language per utterance. Caller text is translated to the user's language (original shown on tap); replies are translated into the callee's language before Timbre. If the callee switches language mid-call, the app follows. One flagship demo pair (e.g. Hindi/English user → Tamil callee) must be reliable; others best-effort.

**F9 — Gate mode.** An "Incoming call" screen state with an **Auto-answer** toggle. On auto-answer Timbre plays an intro ("I can't hear calls; please tell me what you need and I'll reply by text") in the callee's detected language; one-tap replies: *Leave it at the door · Ring the bell · I'll come down · Wait 5 minutes · Please call again.* The demo scene is clearly labelled as scripted; the underlying flow is the real relay.

**F10 — Assistive intro & consent.** Every call begins with a short, dignified Timbre intro (editable name) stating it is an assistive service and calls are not recorded. The callee page shows the same text and requires a "Join call" tap (mic permission).

**F11 — Summary & history.** After a call: summary (from `summarize_call`), extracted entities, optional saved transcript (**opt-in**, off by default), and the call's measured latencies. History lists the user's past calls.

**F12 — Reliability.** Auto-reconnect of Gnani STT before/after the 15-minute cap (overlap handoff, no lost words); network-drop banner and recovery; clear errors for mic denied, key invalid, limit exceeded, Gnani/LLM timeout (graceful fallback: captions still work if the LLM is down); connection-quality pill.

---

## 8. UI/UX and design system

**Product feel:** a calm, trustworthy communication app in the family of messaging and health apps. Mobile-first (design at 390×844), responsive up to desktop (two-column: conversation + side panel for context card/summary draft). Installable PWA (manifest, icons, offline shell, `display: standalone`).

**Design tokens (starting values; keep them in CSS variables):**
```
--bg:#F6F5F2  --surface:#FFFFFF  --ink:#1B1F23  --ink-2:#4A5159  --line:#E3E1DB
--accent:#0B6B5E  --accent-ink:#FFFFFF  --accent-tint:#E1F0ED
--caller-bubble:#EEF0F2  --you-bubble:var(--accent-tint)
--warn:#B45309  --danger:#B42318  --ok:#1F7A4D
radius: 10px (controls) · 14px (cards) · pill for chips
spacing: 4/8/12/16/24/32 · borders 1px var(--line) · shadows: none by default, one subtle level for sheets
```
Provide a dark theme with equivalent tokens; follow `prefers-color-scheme` with a manual override. All text/background pairs meet **WCAG AA** (4.5:1; 3:1 for large text).

**Typography:** Noto Sans for Latin plus Noto Sans Devanagari, Tamil, Telugu, Kannada, Malayalam, Bengali, Gujarati, Gurmukhi, self-hosted via `@fontsource` (no CDN). Use font fallbacks and test every script for clipped diacritics/line-height. Tabular numerals for number cards. Body 16 px; captions user-scalable; number cards ≥ 40 px.

**Icons:** Lucide only. No emoji in UI chrome. **Avoid:** purple/blue gradients, glassmorphism, centred hero with identical feature cards, heavy shadows, sparkle/"AI" motifs, lorem ipsum.

**Screens (build only these):**
1. **Sign-in/onboarding** — name, preferred language, caption size, permissions explanation.
2. **Home** — Start a call (primary), Gate mode toggle, recent calls, saved templates (clinic/bank/delivery).
3. **Call setup** — goal, context card, user language, callee language, voice, tone, mode; generates a **join link/QR** for the callee.
4. **Live call** (main screen). Top bar: callee label, timer, connection/latency pill, language chips, End call (distinct danger style). Body: conversation list — caller left, you right, centred system events ("Caller is speaking…", "Waiting for caller to join", "Caller switched to Tamil"). Pinned: number/entity card, warning card. Above composer: suggestion chips. Composer: text field, mic (hold or toggle), tone popover, send; mode switch **Type | Speak | Speak+Translate**. Visual indicators replace sound: speaking / your turn / sending / delivered / connection quality; optional vibration patterns when the caller finishes a question or waits too long (feature-detect `navigator.vibrate`).
5. **Summary & settings** — summary, entities, history link; settings for caption size, theme, undo window, transcript saving, mock mode indicator (dev only).

**Callee page `/join/:code`:** minimal branded page, consent text, **Join call** button, mute, leave, and (optional) live text of what the user said so the caller can verify. Works on mobile browsers; handles expired code.

**Copy tone:** plain, warm, respectful; never infantilising; no jargon in user-facing text. All strings via the i18n map.

**Empty / loading / error states** exist for every screen. Motion is minimal and respects `prefers-reduced-motion`. Touch targets ≥ 48 px. Full keyboard and screen-reader support (labels, live regions for captions with polite announcements configurable).

---

## 9. Security, privacy, multi-user

- Supabase Auth (email + Google) from M6; before that, a dev-stub user. API validates the JWT on every request and WebSocket. Row-level security on all tables; users access only their own rows.
- Tables: `profiles`, `templates`, `call_sessions`, `call_turns` (stored only if the user opted in), `usage_counters`.
- API keys only in server env. CORS allow-list from env. Rate limits per user and per IP; join codes are random, single-use, expire in 15 minutes.
- No call audio persisted. Logs never contain transcripts or keys (log lengths/IDs only).
- Privacy notice screen and consent copy; in-app delete-my-data action.
- Play Store readiness notes (document in `docs/PLAYSTORE.md` in M9, do not implement): wrap with Capacitor/TWA, mic-permission declaration, Data Safety form, and the fact that Android cannot inject audio into a carrier call — a real release would use a telephony provider to reach the callee.

---

## 10. Reliability and performance targets (measure; do not claim unmeasured numbers)

- Caption latency: caller end-of-speech → text on user screen (report p50/p95).
- Reply latency: send → first audio byte at callee, per mode (type/tap, speak-direct, speak-transform, cross-language).
- Suggestion latency: transcript → chips visible.
- Reconnect: no lost caption segments across a forced reconnect (test).
- Cost guards enforced; hitting a cap shows a human-readable message, not a crash.

---

## 11. Mock mode and cost guards

`MOCK_MODE=true`: fake Gnani STT (replays canned transcripts with realistic timing/`processing` events), fake TTS (short tones or pre-generated clips), fake LLM (deterministic JSON). The entire UI and all Playwright tests run in mock mode. A banner shows "Mock mode" in dev builds. Cost guards live in `limits.py`, persist counters, and are covered by tests.

---

## 12. Evaluation harness (`eval/`, human-run with real keys)

Goal: produce honest numbers for the interview and README, in `docs/RESULTS.md`.

1. **Test set:** ≥ 20 scripted utterances (Hindi-English code-mixed, English, Tamil, plus numbers, amounts, names, times, medical/bank terms). Generate audio with Timbre, **and** include ≥ 5 clips recorded by real humans if available. Clearly label synthetic vs real.
2. **Degradation pipeline** (ffmpeg/numpy): resample to 8 kHz, 300–3400 Hz band-pass, additive noise at SNR 20/10/5 dB, simulated packet loss (drop 20 ms frames). Use generated noise or noise the user owns/records; do not download copyrighted audio.
3. **Runs:** Prisma v3.0 (REST and Realtime where practical) with and without context hints; fixed vs `indic-auto` language.
4. **Metrics:** WER/CER (`jiwer`), **entity accuracy** (amount/time/phone exact match), latency (Gnani `latency` field and measured end-to-end), counts and confidence intervals where n allows.
5. **Report:** tables per condition, plus an explicit **limitations** section (synthetic speech is cleaner than real speech; small n; one speaker/voice). Never present results beyond what the data supports.

---

## 13. Repo structure (create in Milestone 0)

```
apps/web/        src/{app,screens,components,hooks,lib,i18n,styles}  public/  index.html
apps/api/        app/{main.py,config.py,limits.py,entities.py,
                      gnani/{stt.py,tts.py,audio.py},
                      llm/{provider.py,tasks.py,prompts/},
                      calls/{session.py,relay.py,transport.py,tones.py},
                      auth.py,db.py,mock/}  tests/
eval/            {build_testset.py,degrade.py,run_stt.py,score.py,report.py}
scripts/smoke/   {stt_rest.py,stt_stream.py,tts_rest.py,tts_stream.py,tag_audition.py,llm_bakeoff.py,keyterms_ab.py}
docs/            gnani/  screens/  RESULTS.md  PLAYSTORE.md
Makefile  README.md
```

---

## 14. Milestones (≈ 20 h total; commit after each; stop after each)

| # | Milestone | Budget |
|---|---|---|
| **M0** | **Scaffold + smoke tests** — repo structure, config loading, mock mode skeleton, Makefile, all `scripts/smoke/*`, `FINDINGS.md` template. **No UI.** | 1.5 h |
| **M1** | **Core call loop** — design tokens/fonts, live call screen skeleton, callee `/join` page, WS relay, caller mic → Prisma → captions, typed reply → Timbre → callee audio, `CalleeTransport`, dev-stub auth, F1 F2 F10 | 3.5 h |
| **M2** | **Suggestions + entity cards** — LLM provider, `suggest_replies`, extractor + tests, confirmation/warning cards, quick phrases (F3, F4) | 1.5 h |
| **M3** | **Tone + context + setup** — tone mapping from audition results, call setup screen, context card → keyterms/bias, "use hints" toggle (F5, F6) | 1.5 h |
| **M4** | **Cross-language** — `indic-auto`, translation both ways, original/translated display, language-switch handling (F8) | 2 h |
| **M5** | **Speak modes** — speak-direct, speak & transform, gating, review/auto-send toggle, headphone guidance (F7) | 3 h |
| **M6** | **Product shell** — Supabase auth + RLS, home, history, summary, settings, PWA manifest/offline shell, usage counters (F11, §9) | 1.5 h |
| **M7** | **Gate mode** — incoming-call state, auto-answer, intro, one-tap replies (F9) | 1 h |
| **M8** | **Evaluation** — harness, runs documented, `docs/RESULTS.md` with limitations | 2 h |
| **M9** | **Polish & hardening** — reliability (F12), error/empty states, a11y audit, phone-size screenshots, `docs/PLAYSTORE.md`, README | 1.5 h |
| — | Buffer | 1 h |

**M0 detail — smoke tests (the human runs these with real keys):**
1. `stt_rest.py` — Prisma v3.0 REST on a short clip, `indic-auto` and fixed language, all four `format`s.
2. `stt_stream.py` — Realtime streaming from a WAV file at 8 kHz and 16 kHz, paced frames; print every message; **test both `x-keyterms` and `x-bias-list`+`x-bias-score`**; test whether `x-model: prisma-v3.0` is required; test `x-format: transcribe`; probe `x-partials` (undocumented) and report.
3. `tts_rest.py` / `tts_stream.py` — Timbre v3.0 in Hindi, Tamil, English; record returned audio format/sample rate, first-byte latency; try the Realtime/SSE endpoints.
4. `tag_audition.py` — generate files for each v3.0 audio tag and each tone candidate on 3 voices so the human can listen and pick tone defaults.
5. `llm_bakeoff.py` — run ~10 sentences (Hindi↔Tamil↔Kannada, number-heavy, formal vs casual) through the configured provider(s); print outputs and latency for the human to judge; the human picks the default.
6. Write everything learned into `docs/gnani/FINDINGS.md`: confirmed headers, formats, latencies, limits, quirks, chosen defaults.

**Fallback priority if behind schedule** (cut from the bottom): M7 Gate mode → simplify M4 to one language pair → trim M6 history. **Never cut:** the live call screen, M5 speak-direct, or M8 measurements.

---

## 15. Definition of done (every milestone)

- Acceptance criteria met; `make lint` and `make test` pass; works in mock mode.
- UI work: Playwright screenshots at 390×844 and 1280×800 reviewed and fixed.
- No secrets in the diff. New env vars added to `.env.example`. Commands in `AGENTS.md` still accurate.
- Report back: what works, what is stubbed, what is unverified, exact commands to try it. No overclaiming.