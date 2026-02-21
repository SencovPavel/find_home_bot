"""Общие фикстуры для тестов проекта."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.parser.models import Listing, MetroTransport, Source, UserFilter


@pytest.fixture
def sample_listing() -> Listing:
    """Возвращает тестовое объявление."""
    return Listing(
        listing_id=123,
        source=Source.CIAN,
        url="https://www.cian.ru/rent/flat/123/",
        title="2-комн. квартира <центр>",
        price=100_000,
        address="Москва & ЦАО",
        metro_station="Тверская",
        metro_distance_min=7,
        metro_transport=MetroTransport.WALK,
        total_area=55.0,
        kitchen_area=12.0,
        rooms=2,
        floor=3,
        total_floors=12,
        renovation="euro",
        description="Можно с детьми, без животных",
        photos=[],
    )


@pytest.fixture
def sample_filter() -> UserFilter:
    """Возвращает тестовый фильтр пользователя."""
    return UserFilter(
        user_id=42,
        city=1,
        price_min=50_000,
        price_max=150_000,
        area_min=40.0,
        kitchen_area_min=8.0,
        renovation_types=["euro"],
        rooms=[2, 3],
        pets_allowed=True,
        is_active=True,
    )


@pytest.fixture
def temp_db_path(tmp_path: Path) -> str:
    """Возвращает путь к временной БД SQLite."""
    return str(tmp_path / "test.sqlite3")
