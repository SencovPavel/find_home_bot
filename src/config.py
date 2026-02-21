"""Конфигурация приложения — загрузка переменных окружения из .env."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_ENV_PATH)


def _require_env(name: str) -> str:
    """Возвращает значение переменной окружения или завершает процесс с ошибкой."""
    value = os.getenv(name)
    if not value:
        raise SystemExit(f"Переменная окружения {name} не задана. Проверьте .env файл.")
    return value


@dataclass(frozen=True)
class Config:
    """Неизменяемая конфигурация приложения."""

    bot_token: str
    admin_user_id: int
    check_interval_minutes: int
    db_path: str
    webapp_url: str | None
    webapp_host: str
    webapp_port: int

    @classmethod
    def from_env(cls) -> Config:
        """Создаёт конфигурацию из переменных окружения."""
        return cls(
            bot_token=_require_env("BOT_TOKEN"),
            admin_user_id=int(_require_env("ADMIN_USER_ID")),
            check_interval_minutes=int(os.getenv("CHECK_INTERVAL_MINUTES", "5")),
            db_path=os.getenv("DB_PATH", str(Path(__file__).resolve().parent.parent / "data.db")),
            webapp_url=os.getenv("WEBAPP_URL") or None,
            webapp_host=os.getenv("WEBAPP_HOST", "0.0.0.0"),
            webapp_port=int(os.getenv("WEBAPP_PORT", "8080")),
        )


config = Config.from_env()
