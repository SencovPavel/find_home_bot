"""Абстрактный интерфейс парсера объявлений."""

from __future__ import annotations

import asyncio
import logging
import random
from typing import List, Protocol

import aiohttp

from src.parser.models import Listing, UserFilter

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.2 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:134.0) Gecko/20100101 Firefox/134.0",
]

MAX_HTML_SIZE_BYTES = 10_000_000

_CAPTCHA_MARKERS = (
    "captcha",
    "showcaptcha",
    "challenge-platform",
    "cf-challenge",
    "please verify",
    "проверка",
)


class ListingParser(Protocol):
    """Протокол парсера объявлений — каждая площадка реализует этот интерфейс."""

    async def search(self, user_filter: UserFilter, pages: int = 2) -> List[Listing]:
        ...


async def fetch_page(
    session: aiohttp.ClientSession,
    url: str,
    *,
    referer: str = "",
    delay_range: tuple[float, float] = (2.0, 6.0),
) -> str | None:
    """Загружает HTML-страницу с рандомной задержкой и anti-block заголовками."""
    delay = random.uniform(*delay_range)
    await asyncio.sleep(delay)

    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
    }
    if referer:
        headers["Referer"] = referer

    try:
        async with session.get(
            url, headers=headers, timeout=aiohttp.ClientTimeout(total=30)
        ) as resp:
            if resp.status != 200:
                logger.warning("Статус %d для %s", resp.status, url)
                return None
            content_length = resp.headers.get("Content-Length")
            if content_length and content_length.isdigit():
                if int(content_length) > MAX_HTML_SIZE_BYTES:
                    logger.warning("Слишком большой ответ (%s байт): %s", content_length, url)
                    return None
            body = await resp.text()
            body_bytes = len(body.encode("utf-8"))
            if body_bytes > MAX_HTML_SIZE_BYTES:
                logger.warning("Слишком большой HTML (%d байт): %s", body_bytes, url)
                return None
            if is_captcha_page(body):
                logger.warning("Обнаружена captcha/challenge: %s", url)
                return None
            return body
    except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
        logger.error("Ошибка запроса %s: %s", url, exc)
        return None


def is_captcha_page(html: str) -> bool:
    """Эвристика: проверяет, является ли страница captcha / challenge."""
    lower = html[:5000].lower()
    return any(marker in lower for marker in _CAPTCHA_MARKERS)


def parse_float(value: object) -> float:
    """Безопасный парсинг float из произвольного значения."""
    if value is None:
        return 0.0
    try:
        return float(str(value).replace(",", "."))
    except (ValueError, TypeError):
        return 0.0
