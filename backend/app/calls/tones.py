from enum import StrEnum
import re


class Tone(StrEnum):
    NEUTRAL = "neutral"
    WARM = "warm"
    POLITE = "polite"
    URGENT = "urgent"
    APOLOGETIC = "apologetic"


TTS_TAGS = frozenset({
    "<coughs>", "<excited>", "<exhales>", "<giggle>", "<laugh>", "<pauses>",
    "<shouting>", "<sigh>", "<slow>", "<sniffles>", "<whispers>", "<yawns>", "<clears throat>",
})
TONE_TAG = {Tone.NEUTRAL: None, Tone.WARM: "<slow>", Tone.POLITE: "<pauses>", Tone.URGENT: None, Tone.APOLOGETIC: "<sigh>"}
TONE_REGISTER = {Tone.NEUTRAL: "neutral", Tone.WARM: "casual", Tone.POLITE: "formal", Tone.URGENT: "neutral", Tone.APOLOGETIC: "formal"}
TONE_VOICE = {Tone.NEUTRAL: "Shivani", Tone.WARM: "Chetana", Tone.POLITE: "Tarika", Tone.URGENT: "Avinash", Tone.APOLOGETIC: "Kalpana"}
ALL_VOICES = ("Shivani", "Lakshmi", "Kalpana", "Chetana", "Vasudha", "Riyaa", "Tarika", "Avinash", "Shubham", "Prakash", "Devansh", "Yashraj", "Harshad")
VOICE_GENDER_IDS = {"female": "Shivani", "male": "Avinash"}


def normalize_voice(value: str) -> str:
    gender = value.strip().lower()
    if gender in VOICE_GENDER_IDS:
        return gender
    return "male" if value in {"Avinash", "Shubham", "Prakash", "Devansh", "Yashraj", "Harshad"} else "female"


def timbre_voice_id(value: str) -> str:
    gender = normalize_voice(value)
    return VOICE_GENDER_IDS[gender]
_TAG_PATTERN = re.compile(r"<[^>]*>")


def sanitize_tts_text(text: str, tone: Tone | str = Tone.NEUTRAL, candidate_tag: str | None = None) -> str:
    """Remove markup from user/LLM text and add at most one whitelisted tone tag."""
    clean = _TAG_PATTERN.sub("", text).strip()
    try:
        selected_tone = Tone(tone)
    except ValueError:
        selected_tone = Tone.NEUTRAL
    tag = candidate_tag if candidate_tag in TTS_TAGS else TONE_TAG[selected_tone]
    return f"{tag} {clean}".strip() if tag and clean else clean
