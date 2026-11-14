> ## Documentation Index
> Fetch the complete documentation index at: https://docs.gnani.ai/llms.txt
> Use this file to discover all available pages before exploring further.

# Models

> The Gnani speech-to-text models, what each one is for, and how to choose between them.

## What a model is

**Gnani Prisma** is the family of speech-to-text models. Each version, such as Prisma v2.5 and Prisma v3.0, is a separate model with its own capabilities and limits.

A model is not the same thing as the way you send audio. You pick the two independently:

* **The model** decides how audio is understood. You choose it with the `model` value.
* **The access method** decides how audio gets to the model: [REST](https://docs.gnani.ai/api/STT/speech-to-text.md), [Realtime streaming](https://docs.gnani.ai/api/STT/stt-websocket.md) or [Batch](https://docs.gnani.ai/api/STTBatch/Introduction.md).

Every model works with every access method. See [What works where](https://docs.gnani.ai/api/STT/overview.md#what-works-where) for the differences.

## Available models

> [card] [Prisma v3.0](https://docs.gnani.ai/api/STT/models/prisma-v3.md)
>
> Multilingual speech-to-text for nine Indian languages and English. Identifies the language itself, handles mixed-language speech, and accepts hints such as names and topics. Select it with `model=prisma-v3.0`. It is described on its [own page](https://docs.gnani.ai/api/STT/models/prisma-v3.md).

> [card] [Prisma v2.5 (default)](https://docs.gnani.ai/api/STT/models/prisma-v2-5.md)
>
> Speech-to-text for nine Indian languages and English, transcribing in the language you specify. Offers number formatting, word boosting and find-and-replace. It is described on its [own page](https://docs.gnani.ai/api/STT/models/prisma-v2-5.md).

> [!NOTE]
>
> Moving to Prisma v3.0? See [how it differs from Prisma v2.5](https://docs.gnani.ai/api/STT/models/prisma-v3.md#how-it-differs-from-prisma-v2-5).

## Which model should I use?

| If you need… | Use |
| - | - |
| A dedicated model for each Indian language, built for monlingual audio | Prisma v2.5 |
| The model to identify the spoken language | [Prisma v3.0](https://docs.gnani.ai/api/STT/models/prisma-v3.md#language-detection) |
| Speech that mixes languages, such as Hindi with English words | [Prisma v3.0](https://docs.gnani.ai/api/STT/models/prisma-v3.md#output-styles) |
| To give the brands or the topic of the call as hints | [Prisma v3.0](https://docs.gnani.ai/api/STT/models/prisma-v3.md#context) |
| Indian-language speech written in Latin letters (romanised) | [Prisma v3.0](https://docs.gnani.ai/api/STT/models/prisma-v3.md#romanised-output-transliterate) |

## How to select a model

The `model` value decides which model transcribes your audio.

| Access method | Prisma v2.5 | Prisma v3.0 |
| - | - | - |
| REST (`POST /stt/v3`) | model=prisma-v2.5 or Leave out `model` (the default) | `model=prisma-v3.0` |
| Realtime (`WS /stt/v3/stream`) | Leave out the `model` header (the default), or `model: prisma-v2.5` | `model: prisma-v3.0` |
| Batch (`POST /stt/v3/batch/jobs`) | `config.model: prisma-v2.5`. `model` is required on Batch. | `config.model: prisma-v3.0` |

> [!NOTE]
>
> **The `3` in `/stt/v3` is not the model version.** It is the version of the URL path. Prisma v2.5 and Prisma v3.0 are both served from the same URLs, and only the `model` value decides which one runs.

The default model is currently Prisma v2.5. Existing integrations keep working unchanged, and you move to a newer model only when you add its `model` value.

## Next steps

* [Prisma v3.0](https://docs.gnani.ai/api/STT/models/prisma-v3.md): capabilities, limits and how it differs from Prisma v2.5.
* [Prisma v2.5](https://docs.gnani.ai/api/STT/models/prisma-v2-5.md): the default model, with its output styles, word boosting and find-and-replace.
* [Speech-to-Text overview](https://docs.gnani.ai/api/STT/overview.md): choose between REST, Realtime and Batch.
* [Supported languages](https://docs.gnani.ai/api/STT/languages.md) and [Limits](https://docs.gnani.ai/api/STT/limits.md).


This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.