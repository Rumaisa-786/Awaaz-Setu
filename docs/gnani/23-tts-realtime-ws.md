> ## Documentation Index
> Fetch the complete documentation index at: https://docs.gnani.ai/llms.txt
> Use this file to discover all available pages before exploring further.

# Text-to-Speech (Realtime)

> Real-time text-to-speech with streaming audio via WebSocket.

## Overview

> [!TIP]
>
> **New — [Audio Tags](https://docs.gnani.ai/api/TTS/tts-audio-tags.md):** Add expressive delivery on Timbre v3.0 by placing tags like `<whispers>`, `<laugh>`, or `<pauses>` inline in your text.

Stream audio in real-time with the lowest latency. Perfect for interactive assistants and live applications.

| Use case | Recommended endpoint |
| :- | :- |
| Lowest-latency interactive / live apps | **This endpoint** |
| Full audio in one response (downloads, batch) | [TTS REST](https://docs.gnani.ai/api/TTS/tts-inference.md) |
| Chunked playback as audio is generated | [TTS Streaming (SSE)](https://docs.gnani.ai/api/TTS/tts-sse.md) |

> [!NOTE]
>
> Passing numbers, IDs, dates, or currency as raw strings causes mispronunciations. See the [Input Formatting Guide](https://docs.gnani.ai/api/TTS/tts-input-formating.md) for correct formatting of phone numbers, account numbers, PINs, Aadhaar, vehicle registration numbers, GSTIN, currency, and more.

***

## Models

| Model | `model` value | Languages | Extra parameters |
| :- | :- | :- | :- |
| Timbre v3.0 | `timbre-v3.0` | 10 Indian languages (every voice speaks all 10) | `language`, `speed`, [audio tags](https://docs.gnani.ai/api/TTS/tts-audio-tags.md) in `text` |
| Timbre v2.5 | `timbre-v2.5` | 10 Indian languages | `language`, `speed` |

**Supported languages:** Hindi, English, Tamil, Telugu, Kannada, Malayalam, Marathi, Punjabi, Bengali, and Gujarati.

Each model has its own voices — see the [Voice Catalog](https://docs.gnani.ai/api/TTS/available-voices.md).

***

## Endpoint

```text theme={null}
WSS wss://api.vachana.ai/api/v1/tts
```

***

## Connection Headers

Pass all configuration as WebSocket upgrade headers. Headers cannot be changed mid-session — reconnect with new headers to change settings.

| Header | Required | Description |
| :- | :- | :- |
| `X-API-Key-ID` | Yes | Your Gnani API key |

***

## Connection Flow

1. **Client connects** — opens a WebSocket to `/api/v1/tts` with all required headers.
2. **Client sends a synthesis message** — JSON with `text`, `voice`, `model`, and `audio_config`.
3. **Server streams audio** — returns base64-encoded audio chunks as JSON messages.
4. **Server completes** — sends a final message with `is_final: true`. The client may send another request or close.
5. **Either side closes** — client or server may close the connection at any time.

> [!NOTE]
>
> Send one synthesis request at a time and consume audio chunks as they arrive for the lowest end-to-end latency.

***

## Request Parameters

```json theme={null}
{
  "text": "नमस्ते, आप कैसे हैं?",
  "voice": "Nalini",
  "model": "timbre-v2.5",
  "language": "hi-IN",
  "speed": 1.0,
  "audio_config": {
    "sample_rate": 48000,
    "num_channels": 1,
    "sample_width": 2,
    "encoding": "linear_pcm",
    "container": "wav"
  }
}
```

**text** `string` *required*

The text to synthesize into speech. Pass numbers, dates, and currency as spoken words to avoid mispronunciations — see [Input Formatting Guide](https://docs.gnani.ai/api/TTS/tts-input-formating.md).

**model** `string` *required*

`timbre-v2.5` or `timbre-v3.0`. The model determines which voices you can use.

**voice** `string` *required*

Voice name from the catalog of the model you selected — voices are not shared between models.

| `model` | Example voices | Full list |
| :- | :- | :- |
| `timbre-v2.5` | `Nalini`, `Kaveri`, `Deepak` | [Timbre v2.5 voices](https://docs.gnani.ai/api/TTS/available-voices.md#timbre-v2-5-voices) |
| `timbre-v3.0` | `Shivani`, `Avinash`, `Lakshmi` | [Timbre v3.0 voices](https://docs.gnani.ai/api/TTS/available-voices.md#timbre-v3-0-voices) |

**language** `string` *required*

Language of the input text. Controls text normalization and routing.

| Value | Language |
| :- | :- |
| `auto` | Auto-detect from script (recommended for mixed content) |
| `hi-IN` | Hindi |
| `en-IN` | English |
| `ta-IN` | Tamil |
| `te-IN` | Telugu |
| `kn-IN` | Kannada |
| `ml-IN` | Malayalam |
| `mr-IN` | Marathi |
| `pa-IN` | Punjabi |
| `bn-IN` | Bengali |
| `gu-IN` | Gujarati |
| `hi-en` | Hinglish (code-mixed Hindi–English) |

**speed** `number | string` (default: 1.0)

Playback speed multiplier. Numeric range: `0.85` (slowest) to `1.15` (fastest). String shortcuts: `"slow"` = 0.85, `"medium"` = 1.0, `"fast"` = 1.15.

**audio\_config** `object`

Controls the format of the streamed audio chunks.

**audio\_config fields**

**audio\_config.sample\_rate** `integer` (default: 48000)

Sample rate in Hz. Supported: `8000`, `16000`, `22050`, `24000`, `44100`, `48000`.

**audio\_config.num\_channels** `integer` (default: 1)

Number of audio channels. `1` for mono.

**audio\_config.sample\_width** `integer` (default: 2)

Sample width in bytes. `2` for 16-bit audio.

**audio\_config.encoding** `string` (default: linear\_pcm)

Audio encoding format. For telephony, prefer `container=mulaw` or `container=alaw` over this field, as both produce the same output. Not required when `container` is `mp3`.

| Value | Meaning |
| - | - |
| `linear_pcm` (default) | Uncompressed PCM audio |
| `pcm_s16le` | Signed 16-bit little-endian PCM |
| `pcm_mulaw` | G.711 µ-law. With `container=raw`, the same as `container=mulaw`. |
| `pcm_alaw` | G.711 A-law. With `container=raw`, the same as `container=alaw`. |
| `oggopus` | OGG Opus, a playable file. The same as `container=ogg`. |

**audio\_config.container** `string` (default: wav)

Output container format. See the [Audio Format Reference](#audio-format-reference) for sample rates and content types.

| Value | Output |
| - | - |
| `wav` (default) | WAV file, with header |
| `raw` | Raw audio with no header (16-bit PCM with `linear_pcm`) |
| `mp3` | MP3 file. `bitrate` applies. |
| `ogg` | OGG Opus file |
| `mulaw` | Raw G.711 µ-law. Forces 8000 Hz. |
| `alaw` | Raw G.711 A-law. Forces 8000 Hz. |

**audio\_config.bitrate** `string` (default: 128k)

MP3 bitrate. Only used when `container` is `mp3`.

| Value | Trade-off |
| - | - |
| `32k` | Lowest quality, smallest file |
| `64k` | Lower quality, smaller file |
| `96k` | Medium |
| `128k` (default) | Standard quality |
| `192k` | Highest quality, largest file |

***

## Audio Format Reference

| `container` | `encoding` | Output | `sample_rate` | `bitrate` | Content-Type |
| - | - | - | - | - | - |
| `wav` | `linear_pcm` | WAV file (with header) | 8000–48000 Hz | — | `audio/wav` |
| `raw` | `linear_pcm` | Raw 16-bit PCM | 8000–48000 Hz | — | `application/octet-stream` |
| `mp3` | — | MP3 file | 8000–48000 Hz | `32k`–`192k` | `audio/mpeg` |
| `ogg` | — | OGG Opus file | 8000–48000 Hz | — | `audio/ogg` |
| `mulaw` | — | Raw G.711 µ-law | **forced 8000 Hz** | — | `audio/basic` |
| `alaw` | — | Raw G.711 A-law | **forced 8000 Hz** | — | `audio/alaw` |

**Encoding aliases** — produce identical output to the `container` rows above:

| `container` | `encoding` | Equivalent to |
| - | - | - |
| `raw` | `pcm_mulaw` | `container=mulaw` |
| `raw` | `pcm_alaw` | `container=alaw` |
| `raw` or `ogg` | `oggopus` | `container=ogg` |

`bitrate` only applies when `container=mp3`. `container=mulaw`/`alaw` override `sample_rate` to 8000 Hz.

> [!NOTE]
>
> When `container=ogg` or `encoding=oggopus` is requested, all audio is encoded into a single OGG Opus file and delivered as one chunk after synthesis completes.

***

## Server Messages

### `start`

Sent when the server begins synthesis for the current request.

```json theme={null}
{ "type": "start", "message": "Streaming started", "request_id": "req_abc123" }
```

### Audio chunk

Each audio chunk arrives as a JSON message. Decode `audio` from base64 and append chunks in order.

```json theme={null}
{
  "type": "audio",
  "data": {
    "chunk_index": 1,
    "audio": "<base64-encoded audio bytes>",
    "is_final": false
  }
}
```

### `complete`

Sent when all audio for the current request has been streamed. `is_final` is `true` and `audio` is empty.

```json theme={null}
{
  "type": "complete",
  "data": {
    "chunk_index": 12,
    "audio": "",
    "is_final": true
  }
}
```

### `error`

**Text-to-Speech** (WebSocket `error` message, and the `error` event on SSE) uses `type` and `message`:

```json theme={null}
{ "type": "error", "message": "Invalid text or audio configuration." }
```

The connection remains open after recoverable errors.

**Voice Cloning** (WebSocket) adds an `error` code:

```json theme={null}
{
  "type": "error",
  "error": "SYNTHESIS_FAILED",
  "message": "Human-readable error description"
}
```

***

## Code Example

```javascript JavaScript theme={null}
const ws = new WebSocket("wss://api.vachana.ai/api/v1/tts", {
  headers: {
    "Content-Type": "application/json",
    "X-API-Key-ID": "<your-api-key>",
  },
});

ws.on("open", () => {
  ws.send(JSON.stringify({
    text: "नमस्ते, आप कैसे हैं?",
    voice: "Nalini",
    model: "timbre-v2.5",
    language: "hi-IN",
    speed: 1.0,
    audio_config: {
      sample_rate: 48000,
      num_channels: 1,
      sample_width: 2,
      encoding: "linear_pcm",
      container: "wav",
    },
  }));
});

ws.on("message", (data) => {
  const msg = JSON.parse(data);
  if (msg.type === "audio") {
    const chunk = Buffer.from(msg.data.audio, "base64");
    // append chunk to your audio buffer
  } else if (msg.type === "complete" || msg.type === "error") {
    ws.close(); // done: close instead of waiting for the idle timeout
  }
});

ws.on("error", (error) => console.error("WebSocket error:", error));
ws.on("close", () => console.log("Connection closed"));
```

```python Python theme={null}
import websocket, json, base64

def on_message(ws, message):
    msg = json.loads(message)
    if msg.get("type") == "audio":
        chunk = base64.b64decode(msg["data"]["audio"])
        # append chunk to your audio buffer
    elif msg.get("type") in ("complete", "error"):
        ws.close()  # done: close instead of waiting for the idle timeout

def on_error(ws, error):
    print(f"Error: {error}")

def on_close(ws, close_status_code, close_msg):
    print("Connection closed")

def on_open(ws):
    ws.send(json.dumps({
        "text": "नमस्ते, आप कैसे हैं?",
        "voice": "Nalini",
        "model": "timbre-v2.5",
        "language": "hi-IN",
        "speed": 1.0,
        "audio_config": {
            "sample_rate": 48000,
            "num_channels": 1,
            "sample_width": 2,
            "encoding": "linear_pcm",
            "container": "wav",
        },
    }))

ws = websocket.WebSocketApp(
    "wss://api.vachana.ai/api/v1/tts",
    header={
        "Content-Type": "application/json",
        "X-API-Key-ID": "<your-api-key>",
    },
    on_open=on_open,
    on_message=on_message,
    on_error=on_error,
    on_close=on_close,
)

ws.run_forever()
```

***

## Available Voices

Each model has its own voices, and a voice only works with its own model:

* **Timbre v2.5** — 42 voices across 10 Indian languages, English, and Hinglish, each with a preferred language. See [Timbre v2.5 voices](https://docs.gnani.ai/api/TTS/available-voices.md#timbre-v2-5-voices).
* **Timbre v3.0** — 13 voices that each speak all 10 languages and support audio tags. See [Timbre v3.0 voices](https://docs.gnani.ai/api/TTS/available-voices.md#timbre-v3-0-voices).

Popular examples: `Nalini` (Hindi), `Kaveri` (English), `Deepak` (Hindi), `Poorvi` (Hinglish).

***

## Python SDK

The SDK's realtime client manages the WebSocket lifecycle and async iteration so you can focus on your application logic.

### Installation

```bash theme={null}
pip install gnani-vachana
```

Requires **Python 3.10+**.

### Authentication

```python Constructor argument theme={null}
from gnani.tts import GnaniTTSRealtimeClient

client = GnaniTTSRealtimeClient(api_key="your-api-key")
```

```bash Environment variable theme={null}
export GNANI_API_KEY="your-api-key"
```

```python Environment variable (usage) theme={null}
from gnani.tts import GnaniTTSRealtimeClient

client = GnaniTTSRealtimeClient()
```

### Stream Audio Chunks in Real-Time

```python theme={null}
import asyncio
from gnani.tts import GnaniTTSRealtimeClient

async def main():
    async with GnaniTTSRealtimeClient(api_key="your-api-key") as client:
        with open("output.wav", "wb") as f:
            async for chunk in client.synthesize(
                "नमस्ते, आप कैसे हैं?",
                voice="Nalini",
                model="timbre-v2.5",
                language="hi-IN",
            ):
                f.write(chunk)

asyncio.run(main())
```

### Collect All Audio at Once

```python theme={null}
import asyncio
from gnani.tts import GnaniTTSRealtimeClient

async def main():
    async with GnaniTTSRealtimeClient(api_key="your-api-key") as client:
        audio = await client.synthesize_and_collect(
            "नमस्ते, आप कैसे हैं?",
            voice="Nalini",
            model="timbre-v2.5",
            language="hi-IN",
        )
        with open("output.wav", "wb") as f:
            f.write(audio)

asyncio.run(main())
```

***


This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.