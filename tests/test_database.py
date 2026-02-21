"""Интеграционные тесты SQLite-слоя."""

from __future__ import annotations

import pytest

from src.parser.models import UserFilter
from src.storage.database import Database


@pytest.mark.asyncio
async def test_database_upsert_and_get_filter(temp_db_path: str) -> None:
    """Сохраняет и читает фильтр пользователя."""
    db = Database(temp_db_path)
    await db.connect()
    try:
        user_filter = UserFilter(
            user_id=11,
            city=2,
            rooms=[1, 2],
            price_min=40_000,
            price_max=90_000,
            area_min=35.0,
            kitchen_area_min=7.0,
            renovation_types=["euro"],
            pets_allowed=True,
            is_active=True,
        )
        await db.upsert_filter(user_filter)

        loaded = await db.get_filter(user_filter.user_id)
        assert loaded is not None
        assert loaded.user_id == user_filter.user_id
        assert loaded.rooms == [1, 2]
        assert loaded.price_max == 90_000
        assert loaded.is_active is True
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_database_active_and_seen_flow(temp_db_path: str) -> None:
    """Проверяет set_active, get_active_filters, mark_seen и cleanup."""
    db = Database(temp_db_path)
    await db.connect()
    try:
        user_filter = UserFilter(user_id=12, is_active=False)
        await db.upsert_filter(user_filter)

        active_before = await db.get_active_filters()
        assert len(active_before) == 0

        await db.set_active(user_filter.user_id, active=True)
        active_after = await db.get_active_filters()
        assert len(active_after) == 1
        assert active_after[0].user_id == user_filter.user_id

        assert await db.is_seen("cian", 1001, user_filter.user_id) is False
        await db.mark_seen("cian", 1001, user_filter.user_id)
        assert await db.is_seen("cian", 1001, user_filter.user_id) is True

        await db.cleanup_old(days=0)
    finally:
        await db.close()
