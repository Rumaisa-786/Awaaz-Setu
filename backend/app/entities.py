from __future__ import annotations

from dataclasses import asdict, dataclass
import re
import unicodedata


_DEVANAGARI_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")
_DIGIT_GROUP = r"[0-9०-९](?:[0-9०-९, .-]*[0-9०-९])?"
_AMOUNT = re.compile(rf"(?:₹|\b(?:rs\.?|inr)\s*)\s*({_DIGIT_GROUP}(?:\.\d{{1,2}})?)", re.I)
_TIME = re.compile(r"\b(?:[01]?\d|2[0-3])[:.]\d{2}(?:\s*[ap]\.?m\.?)?\b", re.I)
_DATE = re.compile(r"\b(?:\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?|\d{4}-\d{2}-\d{2})\b")
_PHONE = re.compile(r"(?<!\d)(?:\+?91[\s-]?)?([6-9][0-9०-९](?:[\s-]?[0-9०-९]){8})(?!\d)")
_REFERENCE = re.compile(r"\b(?:reference|ref|ticket|order|booking|case|id)\s*(?:(?:number|no\.?|id)|#|:)?\s*([A-Z0-9-]{4,20})\b", re.I)
_RISK = re.compile(r"\b(?:otp|one[ -]?time\s+(?:password|passcode)|pin|cvv|cvc|bank\s+password|password|card\s+number)\b", re.I)


@dataclass(frozen=True)
class Entity:
    type: str
    value: str
    start: int
    end: int

    def to_dict(self) -> dict[str, str | int]:
        return asdict(self)


def _normalize_digits(value: str) -> str:
    return unicodedata.normalize("NFKC", value).translate(_DEVANAGARI_DIGITS)


def extract_entities(text: str) -> list[Entity]:
    normalized = _normalize_digits(text)
    entities: list[Entity] = []
    patterns = (("amount", _AMOUNT), ("time", _TIME), ("date", _DATE), ("phone", _PHONE), ("reference_id", _REFERENCE))
    for kind, pattern in patterns:
        for match in pattern.finditer(normalized):
            value = match.group(0).strip() if kind == "amount" else match.group(1) if kind in {"phone", "reference_id"} else match.group(0)
            entities.append(Entity(kind, value.strip(), match.start(), match.end()))
    entities.sort(key=lambda item: (item.start, -(item.end - item.start)))
    deduped: list[Entity] = []
    for entity in entities:
        if any(entity.start < old.end and old.start < entity.end for old in deduped):
            continue
        deduped.append(entity)
    return deduped


def detect_security_risk(text: str) -> bool:
    return bool(_RISK.search(_normalize_digits(text)))


def analyze_utterance(text: str) -> dict[str, object]:
    return {"entities": [item.to_dict() for item in extract_entities(text)], "otp_pin_cvv_request": detect_security_risk(text)}
