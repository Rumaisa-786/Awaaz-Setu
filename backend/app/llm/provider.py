import asyncio
import json
import random
from typing import Any, Protocol

from pydantic import BaseModel, ValidationError
from app.config import Settings, get_settings


class LLMProvider(Protocol):
    async def generate_json(self, prompt: str, schema: type[BaseModel]) -> BaseModel: ...


class MockLLMProvider:
    async def generate_json(self, prompt: str, schema: type[BaseModel]) -> BaseModel:
        del prompt
        sample = _mock_json_for(schema)
        return self.parse_json(json.dumps(sample, ensure_ascii=False), schema)

    @staticmethod
    def parse_json(payload: str, schema: type[BaseModel]) -> BaseModel:
        return schema.model_validate(json.loads(payload))


class GeminiProvider:
    def __init__(self, api_key: str, model: str, attempts: int = 4, timeout_seconds: float = 3.0):
        from google import genai
        self.client = genai.Client(api_key=api_key)
        self.model = model
        self.attempts = attempts
        self.timeout_seconds = timeout_seconds

    async def generate_json(self, prompt: str, schema: type[BaseModel]) -> BaseModel:
        deadline = asyncio.get_running_loop().time() + self.timeout_seconds
        for attempt in range(self.attempts):
            try:
                from google.genai import types
                remaining = deadline - asyncio.get_running_loop().time()
                if remaining <= 0:
                    raise TimeoutError("LLM request exceeded its time budget")
                response = await asyncio.wait_for(
                    asyncio.to_thread(
                        self.client.models.generate_content,
                        model=self.model,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            response_schema=schema,
                        ),
                    ),
                    timeout=remaining,
                )
                return schema.model_validate(json.loads(response.text or ""))
            except Exception as exc:
                invalid_json = isinstance(exc, (json.JSONDecodeError, ValidationError))
                retryable = _is_transient(exc) or (invalid_json and attempt == 0)
                if attempt + 1 >= self.attempts or not retryable:
                    raise
                if not invalid_json:
                    delay = min(8.0, 0.5 * (2**attempt)) + random.uniform(0, 0.25)
                    remaining = deadline - asyncio.get_running_loop().time()
                    if delay >= remaining:
                        raise
                    await asyncio.sleep(delay)


def create_provider(settings: Settings | None = None) -> LLMProvider:
    selected = settings or get_settings()
    if selected.mock_mode:
        return MockLLMProvider()
    if selected.llm_provider.lower() != "gemini":
        raise ValueError(f"Unsupported LLM_PROVIDER: {selected.llm_provider}")
    api_key = selected.gemini_api_key.get_secret_value()
    if not api_key:
        raise ValueError("GEMINI_API_KEY is required when MOCK_MODE is false")
    return GeminiProvider(api_key=api_key, model=selected.llm_model)


def _is_transient(exc: Exception) -> bool:
    status = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    return status in {429, 500, 502, 503, 504} or isinstance(exc, (TimeoutError, ConnectionError))


def _mock_json_for(schema: type[BaseModel]) -> dict[str, Any]:
    fields = schema.model_fields
    result: dict[str, Any] = {}
    for name, field in fields.items():
        annotation = field.annotation
        if annotation is str:
            result[name] = "Mock response"
        elif annotation is bool:
            result[name] = False
        elif annotation is int:
            result[name] = 0
        elif "list" in str(annotation).lower():
            result[name] = []
        elif field.is_required():
            result[name] = None
    return result
