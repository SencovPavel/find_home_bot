"""Валидация initData от Telegram Web App."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from urllib.parse import unquote

AUTH_DATE_MAX_AGE_SEC = 24 * 3600  # 24 часа


def validate_init_data(
    init_data: str,
    bot_token: str,
    *,
    check_auth_date: bool = True,
) -> dict | None:
    """Проверяет подпись initData и возвращает распарсенные данные (user и т.д.).

    Возвращает dict с ключами user (dict с id, first_name, ...), auth_date и др.
    или None при невалидных данных.
    """
    if not init_data or not bot_token:
        return None
    try:
        parsed: dict[str, str] = {}
        for part in init_data.split("&"):
            if "=" not in part:
                continue
            key, val = part.split("=", 1)
            parsed[key] = unquote(val)
        hash_str = parsed.pop("hash", None)
        if not hash_str:
            return None

        data_check_string = "\n".join(f"{k}={parsed[k]}" for k in sorted(parsed.keys()))
        secret_key = hmac.new(
            b"WebAppData",
            bot_token.encode(),
            hashlib.sha256,
        ).digest()
        calculated_hash = hmac.new(
            secret_key,
            data_check_string.encode(),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(calculated_hash, hash_str):
            return None

        if check_auth_date:
            auth_date = parsed.get("auth_date")
            if auth_date:
                try:
                    ts = int(auth_date)
                    if time.time() - ts > AUTH_DATE_MAX_AGE_SEC:
                        return None
                except ValueError:
                    return None

        result: dict = {}
        if "user" in parsed:
            try:
                result["user"] = json.loads(parsed["user"])
            except json.JSONDecodeError:
                return None
        if "auth_date" in parsed:
            try:
                result["auth_date"] = int(parsed["auth_date"])
            except ValueError:
                pass
        return result
    except Exception:
        return None
