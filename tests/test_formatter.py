"""Тесты форматирования сообщений для Telegram."""

from __future__ import annotations

from src.bot.formatter import format_listing, format_listing_approx, format_listing_short
from src.parser.models import Listing, MetroTransport, Source


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
        listing_id=1,
        source=Source.CIAN,
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


def test_format_listing_short_contains_key_info(sample_listing: Listing) -> None:
    """Краткий формат содержит комнаты, площадь, цену и метро."""
    result = format_listing_short(sample_listing)

    assert "2-комн." in result
    assert "55.0 м²" in result
    assert "100 000" in result
    assert "Тверская" in result
    assert "ЦИАН" in result


def test_format_listing_approx_shows_deviations(sample_listing: Listing) -> None:
    """Формат «почти подходит» содержит отклонения и основную информацию."""
    deviations = ["Цена выше на 5%", "Площадь меньше на 3%"]

    result = format_listing_approx(sample_listing, deviations)

    assert "Почти подходит" in result
    assert "Цена выше на 5%" in result
    assert "Площадь меньше на 3%" in result
    assert sample_listing.title.replace("<", "").replace(">", "") not in result or "центр" in result


def test_format_listing_shows_commission(sample_listing: Listing) -> None:
    """Если есть комиссия, она отображается."""
    sample_listing.commission = "50%"
    result = format_listing(sample_listing)

    assert "50%" in result


def test_format_listing_without_metro() -> None:
    """Без метро блок метро не отображается."""
    listing = Listing(
        listing_id=2,
        source=Source.CIAN,
        url="https://www.cian.ru/rent/flat/2/",
        title="Студия",
        price=40_000,
        address="Адрес",
        metro_station="",
        metro_distance_min=0,
        metro_transport=MetroTransport.WALK,
        total_area=25.0,
        kitchen_area=0.0,
        rooms=1,
        floor=5,
        total_floors=9,
        renovation="euro",
        description="",
    )

    result = format_listing(listing)

    assert "🚇" not in result
    assert "Студия" in result


def test_format_listing_floor_without_total() -> None:
    """Если есть этаж, но нет этажности дома, выводится только этаж."""
    listing = Listing(
        listing_id=3,
        source=Source.CIAN,
        url="https://www.cian.ru/rent/flat/3/",
        title="Квартира",
        price=60_000,
        address="Адрес",
        metro_station="",
        metro_distance_min=0,
        metro_transport=MetroTransport.WALK,
        total_area=40.0,
        kitchen_area=8.0,
        rooms=2,
        floor=7,
        total_floors=0,
        renovation="",
        description="",
    )

    result = format_listing(listing)

    assert "Этаж: 7" in result
    assert "/" not in result.split("Этаж")[1].split("\n")[0]


def test_format_listing_short_without_metro() -> None:
    """Краткий формат без метро не содержит м. ."""
    listing = Listing(
        listing_id=4,
        source=Source.CIAN,
        url="https://www.cian.ru/rent/flat/4/",
        title="Студия",
        price=30_000,
        address="Адрес",
        metro_station="",
        metro_distance_min=0,
        metro_transport=MetroTransport.WALK,
        total_area=20.0,
        kitchen_area=0.0,
        rooms=1,
        floor=1,
        total_floors=5,
        renovation="",
        description="",
    )

    result = format_listing_short(listing)

    assert "м." not in result
