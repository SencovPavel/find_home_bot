"""Форматирование объявлений для отправки в Telegram."""

from __future__ import annotations

import html
from urllib.parse import urlsplit

from src.parser.models import Listing, MetroTransport, RenovationType


def format_listing(listing: Listing) -> str:
    """Форматирует объявление в HTML-сообщение для Telegram."""
    parts: list[str] = []

    parts.append(f"<b>{_escape(listing.title)}</b>\n")
    parts.append(f"💰 <b>{_format_price(listing.price)}</b> руб/мес")
    parts.append(f"📍 {_escape(listing.address)}")

    if listing.metro_station:
        transport_label = MetroTransport.label(listing.metro_transport)
        metro_line = f"🚇 {_escape(listing.metro_station)}"
        if listing.metro_distance_min:
            metro_line += f" — {listing.metro_distance_min} мин {transport_label}"
        parts.append(metro_line)

    area_line = f"📐 {listing.total_area} м²"
    if listing.kitchen_area:
        area_line += f" (кухня {listing.kitchen_area} м²)"
    parts.append(area_line)

    if listing.floor and listing.total_floors:
        parts.append(f"🏢 Этаж: {listing.floor}/{listing.total_floors}")
    elif listing.floor:
        parts.append(f"🏢 Этаж: {listing.floor}")

    if listing.renovation:
        parts.append(f"🔧 Ремонт: {RenovationType.label(listing.renovation)}")

    parts.append("")
    parts.append(f'<a href="{_safe_url_attr(listing.url)}">Открыть на ЦИАН</a>')

    return "\n".join(parts)


def format_listing_short(listing: Listing) -> str:
    """Краткий формат для списка (без фото)."""
    price = _format_price(listing.price)
    metro = ""
    if listing.metro_station:
        metro = f" | м. {listing.metro_station}"
    return f"{listing.rooms}-комн., {listing.total_area} м² | {price} ₽{metro}"


def _format_price(price: int) -> str:
    """Форматирует цену с разделителями тысяч."""
    return f"{price:,}".replace(",", " ")


def _escape(text: str) -> str:
    """Экранирование HTML-символов для Telegram."""
    return html.escape(text, quote=True)


def _safe_url_attr(url: str) -> str:
    """Возвращает безопасный URL для вставки в HTML-атрибут href."""
    cleaned = url.strip()
    parsed = urlsplit(cleaned)
    if parsed.scheme not in {"http", "https"}:
        return "https://www.cian.ru/"
    return html.escape(cleaned, quote=True)
