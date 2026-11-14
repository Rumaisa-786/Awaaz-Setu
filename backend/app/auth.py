from __future__ import annotations

import httpx
from fastapi import HTTPException, Request

from app.config import get_settings


async def resolve_user(request: Request) -> str:
    """Guest identity is explicit when Supabase is not configured; configured mode verifies JWT via Auth."""
    settings = get_settings()
    if not settings.supabase_enabled:
        return "guest-local"
    authorization = request.headers.get("authorization", "")
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(401, "Sign in to continue")
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get(
                settings.supabase_url.rstrip("/") + "/auth/v1/user",
                headers={"apikey": settings.supabase_anon_key.get_secret_value(), "Authorization": f"Bearer {token}"},
            )
        response.raise_for_status()
        user_id = response.json().get("id")
        if not user_id:
            raise ValueError("Missing user id")
        return str(user_id)
    except Exception as exc:
        raise HTTPException(401, "Your sign-in has expired. Please sign in again.") from exc
