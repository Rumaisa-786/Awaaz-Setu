from fastapi import FastAPI
from app.config import get_settings

app = FastAPI(title="Awaaz Setu API", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str | bool]:
    settings = get_settings()
    return {"status": "ok", "mock_mode": settings.mock_mode}
