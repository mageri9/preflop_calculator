from __future__ import annotations
import hashlib, hmac, time
from typing import Any
from urllib.parse import parse_qsl
from fastapi import HTTPException, Request
from src.core.config import settings

def verify_telegram_init_data(init_data_str: str, bot_token: str) -> dict[str, Any]:
    pairs = dict(parse_qsl(init_data_str, keep_blank_values=True))
    received = pairs.pop("hash", None)
    if not received or "auth_date" not in pairs:
        raise ValueError("Missing hash or auth_date")
    try:
        if time.time() - int(pairs["auth_date"]) > 86400:
            raise ValueError("Authentication data expired")
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid auth_date") from exc
    check = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    calculated = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(calculated, received):
        raise ValueError("Invalid signature")
    import json
    user = json.loads(pairs["user"]) if pairs.get("user") else {}
    return user

async def get_current_user_id(request: Request) -> int:
    value = request.headers.get("X-Telegram-Init-Data")
    if not value:
        auth = request.headers.get("Authorization", "")
        value = auth[7:] if auth.lower().startswith("bearer ") else None
    if not value:
        if settings.ENVIRONMENT == "development": return 99999999
        raise HTTPException(401, "Missing Telegram authorization header")
    try:
        user = verify_telegram_init_data(value, settings.BOT_TOKEN)
        return int(user["id"])
    except Exception as exc:
        raise HTTPException(401, "Invalid Telegram authentication signature") from exc
