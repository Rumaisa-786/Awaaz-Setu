# Awaaz Setu Architecture and Release Notes

## Dual-channel routing and echo control

The user app and the caller's join page connect to different WebSocket routes. Caller PCM16 frames (16 kHz mono, 1,024 bytes each) enter the callee channel, then the Prisma caller STT queue. Captions and control events return only to the user's channel. Timbre output is sent only through the outbound callee transport. The user microphone enters through the authenticated user WebSocket: Speak-Direct forwards its PCM frames to the callee player, while Speak & Transform puts them in a second, separate Prisma queue. The user microphone is never inserted into the caller's Prisma queue and is never played back locally.

Microphone capture requests echo cancellation, noise suppression, and automatic gain control; AudioWorklet output is routed to a zero-gain node locally. Speak & Transform pauses user-side STT frame forwarding during caller speech and while Timbre audio is being generated. Web Audio playback handles the callee's received TTS chunks and direct PCM frames.

Gate Mode uses an in-process simulated callee. It is explicitly labelled scripted, uses the ordinary user call UI, generates a visible disclosure and delivery transcript, and queues speech synthesis in the background so TTS latency does not hold up the captions or quick-reply UI. Its scripted caller is not a real courier.

## Session and provider reliability

FastAPI owns short-lived call state, unguessable join codes, owner tokens, concurrent-call limits, session duration, and TTS character budgets. User WebSocket sessions reconnect with capped exponential backoff. Callee WebSocket disconnects preserve the call session so the same join link can reconnect; explicit leave ends the call. Prisma is rotated before its documented 15-minute session cap, with queued audio retained during reconnect. This is a reconnect window, not a zero-gap or no-lost-word guarantee; measure it with real networks before claiming seamless handoff.

Gemini enrichment runs independently of caption delivery. If it fails or reaches a rate limit, fallback suggestions and a visible status preserve captions and typed replies. Provider errors are reduced to service/status information rather than logging credentials or transcripts.

## `CalleeTransport` extension seam

`CalleeTransport` is the outbound audio boundary. `WebLinkTransport` serves the current browser join link. A production telephony adapter could implement the same send-audio/event operations for an authenticated VoIP/SIP session and convert audio into the provider's required telephony codec and sample rate. Potential integrations include Exotel, Twilio, SIP infrastructure, or LiveKit. Each requires provider account setup, consent, caller identity and emergency-call policies, codec/VAD testing, reconnect handling, and secure mapping between telephony call IDs and Awaaz Setu sessions. No such adapter is included here.

## Supabase and persistence

When Supabase is configured, the backend validates user access tokens through the Supabase Auth user endpoint. The frontend writes saved summaries and opted-in transcript rows using the user's session; RLS checks ownership and the transcript's parent call. With Supabase variables blank, guest calls use the local demo identity and opted-in history stays in browser localStorage. Audio is never persisted. Do not store transcripts unless the user has explicitly opted in.

## Android and Play Store packaging

The current PWA is installable and can be wrapped with a Trusted Web Activity (TWA) or Capacitor for packaging experiments. The web app requires microphone permission for the caller's browser session; the permission prompt must follow an explicit user action and explain why the microphone is needed.

Android does not provide ordinary applications with a supported API to inject app audio into an unrelated native cellular call or capture the far-end call audio. A production product must route calls through a VoIP/telephony bridge (for example, an authorized SIP/Twilio/Exotel path) rather than promise native-call audio injection. A store release also needs the correct microphone disclosures, Play Data Safety answers, privacy notice, account deletion flow, child/sensitive-data review, and tested consent and retention controls. This repository is a prototype and is not Play Store ready.

## Evaluation caveats

`backend/scripts/evaluate.py --mock` measures local deterministic entity/risk logic and audio-file degradation plumbing; it does not call a speech recognizer. Live mode creates synthetic speech with Timbre and sends it to Prisma and Gemini, so WER/CER are estimates on generated speech, not human callers or carrier audio. Results must retain the synthetic/live labels and limitations written by the harness.
