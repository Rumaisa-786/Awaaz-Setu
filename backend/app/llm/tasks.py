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


async def suggest_replies(transcript: str, detected_language: str, goal: str, keyterms: list[str], turns: list[dict[str, str]]) -> SuggestionResult:
    fallback = SuggestionResult(replies=fallback_suggestions(detected_language), needs_free_text=True)
    if get_settings().mock_mode:
        return fallback
    prompt = f"""Return strict JSON matching the schema. Write all 3 replies in the same language and script as the caller transcript, regardless of any request language. Caller language code: {detected_language}.
Caller transcript: {transcript}
Call goal and user-provided context: {goal[:500]} | {json.dumps(keyterms[:20], ensure_ascii=False)}
Recent turns: {json.dumps(turns[-6:], ensure_ascii=False)}
Give three short, natural, non-committal responses. Never agree to payment, consent, legal terms, or disclose personal/financial information. Never invent user facts. If a caller asks for OTP, PIN, CVV, card number or password, do not suggest sharing it. Keep numbers as digits."""
    try:
        result = await provider().generate_json(prompt, SuggestionResult)
        cleaned = [" ".join(reply.split()[:12]) for reply in result.replies[:3]]
        return SuggestionResult(replies=cleaned, needs_free_text=result.needs_free_text)
    except Exception:
        return fallback


async def apply_tone(text: str, tone: Tone, language_code: str) -> ToneResult:
    if get_settings().mock_mode or tone is Tone.NEUTRAL:
        return ToneResult(rewritten_text=text, audio_tag=None)
    prompt = f"""Rewrite this user-selected reply in {language_code} using a {TONE_REGISTER[tone]} register suitable for a phone call. Preserve every fact, number, name, amount, and intent. Do not add consent, payment or personal details. Return strict JSON with rewritten_text and audio_tag. audio_tag must be null or one of {sorted(TTS_TAGS)}. Tone: {tone.value}. Reply: {text}"""
    try:
        result = await provider().generate_json(prompt, ToneResult)
        return result if result.audio_tag in TTS_TAGS else result.model_copy(update={"audio_tag": None})
    except Exception:
        return ToneResult(rewritten_text=text)


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
