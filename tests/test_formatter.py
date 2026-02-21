"""Тесты форматирования сообщений для Telegram."""

from __future__ import annotations

from src.bot.formatter import format_listing
from src.parser.models import Listing, MetroTransport


def test_format_listing_escapes_html_and_url(sample_listing: Listing) -> None:
    """Экранирует опасные символы в тексте и ссылке."""
    sample_listing.url = 'https://example.com/?q=<script>&x="1"'

    result = format_listing(sample_listing)

    assert "&lt;центр&gt;" in result
    assert "Москва &amp; ЦАО" in result
    assert 'href="https://example.com/?q=&lt;script&gt;&amp;x=&quot;1&quot;"' in result


def test_format_listing_fallbacks_to_safe_cian_url() -> None:
    """Подставляет безопасный URL, если схема ссылки недопустима."""
    listing = Listing(
        cian_id=1,
        url="javascript:alert(1)",
        title="Студия",
        price=50_000,
        address="Адрес",
        metro_station="",
        metro_distance_min=0,
        metro_transport=MetroTransport.WALK,
        total_area=30.0,
        kitchen_area=0.0,
        rooms=1,
        floor=1,
        total_floors=1,
        renovation="",
        description="",
        photos=[],
    )

    result = format_listing(listing)

    assert 'href="https://www.cian.ru/"' in result
