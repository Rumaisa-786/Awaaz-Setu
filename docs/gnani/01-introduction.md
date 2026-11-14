> ## Documentation Index
> Fetch the complete documentation index at: https://docs.gnani.ai/llms.txt
> Use this file to discover all available pages before exploring further.

# Introduction – Gnani Speech APIs

> Speech-to-text, text-to-speech, and voice cloning APIs for Indian languages — REST, streaming, and batch.

Build with Gnani Speech APIs when you need transcription or synthesis in production — REST for short clips, WebSocket for live audio, and Batch for long or multi-file jobs.

| Product | When to use it |
| - | - |
| **This section** | Integrate STT, TTS, or voice cloning directly in your app |
| [Agent Builder](https://docs.gnani.ai/introduction.md) | Configure agents in the console |
| [Agent Builder Platform API](https://docs.gnani.ai/Platform/platform-introduction.md) | Manage agents, FAQs, and conversations over REST |

## Base URL

```text theme={null}
https://api.vachana.ai
```

All paths in this documentation are relative to this base URL.

## Authentication

Send your API key on every request:

```bash theme={null}
X-API-Key-ID: <your_api_key>
```

Generate a key from the [Gnani API dashboard](https://app.gnani.ai/voice). Missing or invalid keys return `401 Unauthorized`.

> [!TIP]
>
> Store keys in environment variables or a secrets manager. Do not commit them to source control.

## Available APIs

### Speech-to-Text — Gnani Prisma

| Model | Use it for | Guide |
| - | - | - |
| Prisma v2.5 (default) | Transcription in the language you specify | [Models](https://docs.gnani.ai/api/STT/models/overview.md) |
| Prisma v3.0 (`model=prisma-v3.0`) | Multilingual speech-to-text with automatic language detection | [Prisma v3.0](https://docs.gnani.ai/api/STT/models/prisma-v3.md) |

Choose a model, then choose how to send audio. See the [Speech-to-Text overview](https://docs.gnani.ai/api/STT/overview.md).

| API | Best for | Guide |
| - | - | - |
| STT REST | Audio up to 30 seconds, single HTTP response | [Speech-to-Text REST](https://docs.gnani.ai/api/STT/speech-to-text.md) |
| STT Realtime | Live microphone or streaming audio | [STT Realtime](https://docs.gnani.ai/api/STT/stt-websocket.md) |
| STT Batch | Long files, many files, offline pipelines | [Batch STT](https://docs.gnani.ai/api/STTBatch/Introduction.md) |

### Text-to-Speech — Gnani Timbre v2.5

> [!TIP]
>
> Timbre v2.5 is the recommended model. Timbre v2.0 is deprecated and will be removed in a future release.

| API | Best for | Guide |
| - | - | - |
| TTS REST | Full audio in one response | [TTS REST](https://docs.gnani.ai/api/TTS/tts-inference.md) |
| TTS Streaming | Progressive playback via SSE | [TTS Streaming](https://docs.gnani.ai/api/TTS/tts-sse.md) |
| TTS Realtime | Lowest latency over WebSocket | [TTS Realtime](https://docs.gnani.ai/api/TTS/tts-websocket.md) |
| Voice catalog | Pick a voice before you integrate | [Available Voices](https://docs.gnani.ai/api/TTS/available-voices.md) |

### Voice cloning

| API | Best for | Guide |
| - | - | - |
| VC Embeddings | Create a `speaker_embedding` from reference audio | [Voice Clone Embeddings](https://docs.gnani.ai/api/VC/voice-clone-embeddings.md) |
| VC REST | Cloned voice in one HTTP response | [VC REST](https://docs.gnani.ai/api/VC/vc-inference.md) |
| VC Streaming | Cloned voice over SSE | [VC Streaming](https://docs.gnani.ai/api/VC/vc-sse.md) |
| VC Realtime | Cloned voice over WebSocket | [VC Realtime](https://docs.gnani.ai/api/VC/vc-websocket.md) |

## Key capabilities

| Capability | Details |
| - | - |
| Languages | 10 Indian languages plus English, with native-script output |
| Language detection | Automatic, on Prisma v3.0 |
| Audio formats | WAV, MP3, OGG, FLAC, AAC, M4A (STT) |
| Voice cloning | Clone from a short reference sample |
| Latency | P95 \~200 ms for STT; streaming TTS supported |
| Modes | Real-time, REST, and batch |
| Formatting | Auto-punctuation and text normalization on supported endpoints |
| SSML | Supported on TTS for fine-grained control |

## Integrations

| Plugin | Guide |
| - | - |
| LiveKit | [LiveKit plugin](https://docs.gnani.ai/livekit/introduction.md) |
| Pipecat | [Pipecat plugin](https://docs.gnani.ai/pipecat/introduction.md) |

## Use case guides

| Guide | Description |
| - | - |
| [Podcast transcription](https://docs.gnani.ai/api/use-cases/podcast-transcription.md) | Speaker-separated batch transcription |
| [Call analytics](https://docs.gnani.ai/api/use-cases/call-analytics.md) | Batch STT plus LLM analysis |
| [Real-time compliance](https://docs.gnani.ai/api/use-cases/real-time-compliance.md) | Live WebSocket monitoring |

## Get started

New to the APIs? Start here: [Quick Start](https://docs.gnani.ai/api/introduction/quick-start.md)

Handling failures: [Error Reference](https://docs.gnani.ai/api/introduction/errors.md).

***

## Docs feedback

Docs feedback: [Gnani APIs docs feedback](https://discord.com/channels/1511338519899930634/1515991436229611571)

**Last verified:** 5 August 2026


This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.