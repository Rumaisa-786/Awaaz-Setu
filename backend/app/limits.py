from dataclasses import dataclass

from app.config import Settings


@dataclass(frozen=True)
class CostLimits:
    daily_usd: float
    session_usd: float
    daily_requests: int
    session_requests: int
    daily_audio_minutes: float
    session_duration_minutes: float

    @classmethod
    def from_settings(cls, settings: Settings) -> "CostLimits":
        return cls(
            daily_usd=settings.daily_cost_limit_usd,
            session_usd=settings.session_cost_limit_usd,
            daily_requests=settings.daily_request_limit,
            session_requests=settings.session_request_limit,
            daily_audio_minutes=settings.daily_audio_minutes_limit,
            session_duration_minutes=settings.session_duration_minutes_limit,
        )


@dataclass
class Usage:
    daily_usd: float = 0.0
    session_usd: float = 0.0
    daily_requests: int = 0
    session_requests: int = 0
    daily_audio_minutes: float = 0.0
    session_duration_minutes: float = 0.0


def check_limits(usage: Usage, limits: CostLimits) -> None:
    pairs = (
        (usage.daily_usd, limits.daily_usd, "daily cost"),
        (usage.session_usd, limits.session_usd, "session cost"),
        (usage.daily_requests, limits.daily_requests, "daily requests"),
        (usage.session_requests, limits.session_requests, "session requests"),
        (usage.daily_audio_minutes, limits.daily_audio_minutes, "daily audio minutes"),
        (usage.session_duration_minutes, limits.session_duration_minutes, "session duration"),
    )
    for current, maximum, label in pairs:
        if current >= maximum:
            raise CostLimitExceeded(f"{label} limit reached")


class CostLimitExceeded(RuntimeError):
    pass
