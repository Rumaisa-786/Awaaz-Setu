from __future__ import annotations

from functools import lru_cache
import json

from pydantic import BaseModel, Field

from app.calls.tones import TTS_TAGS, TONE_REGISTER, Tone
from app.config import get_settings
from app.entities import Entity
from app.llm.provider import LLMProvider, create_provider


class SuggestionResult(BaseModel):
    replies: list[str] = Field(min_length=3, max_length=3)
    needs_free_text: bool


class ToneResult(BaseModel):
    rewritten_text: str
    audio_tag: str | None = None


class EntityConfirmation(BaseModel):
    confirmed_entities: list[dict[str, str]]
    risk_request: bool


class RelayResult(BaseModel):
    translated_text: str
    rewritten_text: str
    audio_tag: str | None = None
    uncertainty: bool = False


class CallSummary(BaseModel):
    outcomes: list[str] = Field(default_factory=list, max_length=12)
    open_items: list[str] = Field(default_factory=list, max_length=12)
    plain_language_summary: str = ""


@lru_cache(maxsize=1)
def provider() -> LLMProvider:
    return create_provider(get_settings())


def fallback_suggestions(language_code: str) -> list[str]:
    language = language_code.split("-")[0].lower()
    values = {
        "hi": ["कृपया फिर से बताइए।", "जी, मैं समझ रहा हूँ।", "कृपया थोड़ा धीरे बोलें।"],
        "mr": ["कृपया पुन्हा सांगा.", "हो, मला समजले.", "कृपया हळू बोला."],
        "ta": ["தயவுசெய்து மீண்டும் சொல்லுங்கள்.", "சரி, புரிகிறது.", "மெதுவாகப் பேசுங்கள்."],
        "kn": ["ದಯವಿಟ್ಟು ಮತ್ತೊಮ್ಮೆ ಹೇಳಿ.", "ಸರಿ, ಅರ್ಥವಾಯಿತು.", "ದಯವಿಟ್ಟು ನಿಧಾನವಾಗಿ ಮಾತನಾಡಿ."],
        "te": ["దయచేసి మళ్లీ చెప్పండి.", "సరే, అర్థమైంది.", "దయచేసి నెమ్మదిగా మాట్లాడండి."],
        "ml": ["ദയവായി വീണ്ടും പറയൂ.", "ശരി, മനസ്സിലായി.", "ദയവായി പതുക്കെ സംസാരിക്കൂ."],
        "bn": ["দয়া করে আবার বলুন।", "ঠিক আছে, বুঝতে পেরেছি।", "দয়া করে একটু ধীরে বলুন।"],
        "gu": ["કૃપા કરીને ફરીથી કહો.", "બરાબર, સમજાયું.", "કૃપા કરીને ધીમે બોલો."],
        "pa": ["ਕਿਰਪਾ ਕਰਕੇ ਦੁਬਾਰਾ ਦੱਸੋ।", "ਠੀਕ ਹੈ, ਸਮਝ ਆ ਗਿਆ।", "ਕਿਰਪਾ ਕਰਕੇ ਹੌਲੀ ਬੋਲੋ।"],
        "en": ["Please repeat that.", "I understand.", "Please speak slowly."],
    }
    return values.get(language, values["en"])


async def suggest_replies(transcript: str, detected_language: str, goal: str, keyterms: list[str], turns: list[dict[str, str]], reply_language: str | None = None) -> SuggestionResult:
    reply_language = reply_language or detected_language
    fallback = SuggestionResult(replies=fallback_suggestions(reply_language), needs_free_text=True)
    if get_settings().mock_mode:
        return fallback
    prompt = f"""Return strict JSON matching the schema. Write all 3 replies in the user's language and script ({reply_language}); caller language is {detected_language}.
Caller transcript: {transcript}
Call goal and user-provided context: {goal[:500]} | {json.dumps(keyterms[:20], ensure_ascii=False)}
Recent turns: {json.dumps(turns[-6:], ensure_ascii=False)}
Give three short, natural, non-committal responses. Never agree to payment, consent, legal terms, or disclose personal/financial information. Never invent user facts. If a caller asks for OTP, PIN, CVV, card number or password, do not suggest sharing it. Keep numbers as digits."""
    try:
        result = await provider().generate_json(prompt, SuggestionResult)
        cleaned = [" ".join(reply.split()[:12]) for reply in result.replies[:3]]
        return SuggestionResult(replies=cleaned, needs_free_text=result.needs_free_text)
    except Exception:
        raise


async def apply_tone(text: str, tone: Tone, language_code: str) -> ToneResult:
    if get_settings().mock_mode or tone is Tone.NEUTRAL:
        return ToneResult(rewritten_text=text, audio_tag=None)
    prompt = f"""Rewrite this user-selected reply in {language_code} using a {TONE_REGISTER[tone]} register suitable for a phone call. Preserve every fact, number, name, amount, and intent. Do not add consent, payment or personal details. Return strict JSON with rewritten_text and audio_tag. audio_tag must be null or one of {sorted(TTS_TAGS)}. Tone: {tone.value}. Reply: {text}"""
    try:
        result = await provider().generate_json(prompt, ToneResult)
        return result if result.audio_tag in TTS_TAGS else result.model_copy(update={"audio_tag": None})
    except Exception:
        return ToneResult(rewritten_text=text)


async def relay_reply(text: str, source_language: str, target_language: str, tone: Tone) -> RelayResult:
    """Translate and adapt register in one schema-validated provider request."""
    if source_language == target_language:
        result = await apply_tone(text, tone, target_language)
        return RelayResult(translated_text=text, rewritten_text=result.rewritten_text, audio_tag=result.audio_tag)
    if get_settings().mock_mode:
        return RelayResult(translated_text=text, rewritten_text=text)
    prompt = f"""Translate this user-selected response from {source_language} to {target_language}, then rewrite it in a {TONE_REGISTER[tone]} register appropriate for a phone call. This must be ONE combined operation. Preserve intent, facts, names, numbers, amounts and dates exactly. Do not add consent, payment, or personal details. Return strict JSON with translated_text, rewritten_text, audio_tag, uncertainty. audio_tag must be null or one of {sorted(TTS_TAGS)}. Input: {text}"""
    try:
        result = await provider().generate_json(prompt, RelayResult)
        if result.audio_tag not in TTS_TAGS:
            result = result.model_copy(update={"audio_tag": None})
        return result
    except Exception:
        return RelayResult(translated_text=text, rewritten_text=text, uncertainty=True)


async def translate_text(text: str, source_language: str, target_language: str) -> str:
    if source_language == target_language or get_settings().mock_mode:
        return text
    class Translation(BaseModel):
        translated_text: str
        uncertainty: bool = False
    prompt = f"Translate from {source_language} to {target_language}. Keep names, dates, numbers, amounts and phone numbers unchanged. If uncertain, preserve meaning conservatively. Return strict JSON. Text: {text}"
    try:
        return (await provider().generate_json(prompt, Translation)).translated_text
    except Exception:
        return text


async def summarize_call(turns: list[dict[str, str]], language: str) -> CallSummary:
    if get_settings().mock_mode:
        text = " ".join(turn.get("text", "") for turn in turns[-20:])
        return CallSummary(outcomes=[text[:240]] if text else [], open_items=[], plain_language_summary=text[:600] or "No transcript was available.")
    prompt = f"Summarize this call in {language} with outcomes, open_items and plain_language_summary. Do not infer unstated facts. Strict JSON. Turns: {json.dumps(turns[-60:], ensure_ascii=False)}"
    try:
        return await provider().generate_json(prompt, CallSummary)
    except Exception:
        return CallSummary(plain_language_summary="A summary could not be generated.")


async def confirm_entities(transcript: str, entities: list[Entity], risk: bool) -> EntityConfirmation:
    candidates = [{"type": entity.type, "value": entity.value} for entity in entities]
    fallback = EntityConfirmation(confirmed_entities=candidates, risk_request=risk)
    if get_settings().mock_mode or not candidates:
        return fallback
    prompt = f"""Validate, do not invent, the deterministic entities extracted from this caller transcript. Return the same entities that are clearly stated, using exact values; discard wrong candidates. Set risk_request true if the caller asks for OTP, PIN, CVV, bank password, or card number. Transcript: {transcript}. Candidates: {json.dumps(candidates, ensure_ascii=False)}"""
    try:
        result = await provider().generate_json(prompt, EntityConfirmation)
        allowed = {(item["type"], item["value"]) for item in candidates}
        retained = [item for item in result.confirmed_entities if (item.get("type"), item.get("value")) in allowed]
        return EntityConfirmation(confirmed_entities=retained, risk_request=bool(risk or result.risk_request))
    except Exception:
        return fallback
