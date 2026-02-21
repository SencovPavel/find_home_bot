"""Асинхронный слой доступа к SQLite: фильтры пользователей и просмотренные объявления."""

from __future__ import annotations

import json
import logging
from typing import Sequence

import aiosqlite

from src.parser.models import UserFilter

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS user_filters (
    user_id          INTEGER PRIMARY KEY,
    city             INTEGER NOT NULL DEFAULT 1,
    district         TEXT    NOT NULL DEFAULT '',
    metro            TEXT    NOT NULL DEFAULT '',
    price_min        INTEGER NOT NULL DEFAULT 0,
    price_max        INTEGER NOT NULL DEFAULT 0,
    area_min         REAL    NOT NULL DEFAULT 0,
    kitchen_area_min REAL    NOT NULL DEFAULT 0,
    renovation_types TEXT    NOT NULL DEFAULT '[]',
    rooms            TEXT    NOT NULL DEFAULT '[]',
    pets_allowed     INTEGER NOT NULL DEFAULT 1,
    no_commission    INTEGER NOT NULL DEFAULT 0,
    commission_max_percent INTEGER NOT NULL DEFAULT 100,
    tolerance_percent INTEGER NOT NULL DEFAULT 0,
    initial_listings_count INTEGER NOT NULL DEFAULT 0,
    is_active        INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS seen_listings (
    source     TEXT    NOT NULL DEFAULT 'cian',
    listing_id INTEGER NOT NULL,
    user_id    INTEGER NOT NULL,
    sent_at    TEXT    NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (source, listing_id, user_id)
);
"""

_MIGRATIONS = [
    "ALTER TABLE user_filters ADD COLUMN no_commission INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE seen_listings ADD COLUMN source TEXT NOT NULL DEFAULT 'cian'",
    "ALTER TABLE seen_listings RENAME COLUMN cian_id TO listing_id",
    "ALTER TABLE user_filters ADD COLUMN tolerance_percent INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE user_filters ADD COLUMN initial_listings_count INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE user_filters ADD COLUMN commission_max_percent INTEGER NOT NULL DEFAULT 100",
    "UPDATE user_filters SET commission_max_percent = 0 WHERE no_commission = 1",
]


class Database:
    """Обёртка над aiosqlite для работы с фильтрами и просмотренными объявлениями."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._db: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        """Открывает соединение, создаёт таблицы, применяет миграции."""
        self._db = await aiosqlite.connect(self._db_path)
        self._db.row_factory = aiosqlite.Row
        await self._db.executescript(_SCHEMA)
        await self._db.commit()
        await self._apply_migrations()
        logger.info("БД инициализирована: %s", self._db_path)

    async def _apply_migrations(self) -> None:
        """Применяет миграции для обновления существующих БД."""
        for sql in _MIGRATIONS:
            try:
                await self.db.execute(sql)
                await self.db.commit()
                logger.info("Миграция применена: %s", sql[:60])
            except Exception:
                pass

    async def close(self) -> None:
        if self._db:
            await self._db.close()

    @property
    def db(self) -> aiosqlite.Connection:
        if self._db is None:
            raise RuntimeError("Database.connect() не был вызван")
        return self._db

    # ── Фильтры пользователей ──────────────────────────────────────

    async def get_filter(self, user_id: int) -> UserFilter | None:
        """Возвращает фильтры пользователя или None."""
        cursor = await self.db.execute(
            "SELECT * FROM user_filters WHERE user_id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return _row_to_filter(row)

    async def upsert_filter(self, f: UserFilter) -> None:
        """Создаёт или обновляет фильтры пользователя."""
        await self.db.execute(
            """
            INSERT INTO user_filters
                (user_id, city, district, metro, price_min, price_max,
                 area_min, kitchen_area_min, renovation_types, rooms,
                 pets_allowed, no_commission, commission_max_percent, tolerance_percent,
                 initial_listings_count, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                city = excluded.city,
                district = excluded.district,
                metro = excluded.metro,
                price_min = excluded.price_min,
                price_max = excluded.price_max,
                area_min = excluded.area_min,
                kitchen_area_min = excluded.kitchen_area_min,
                renovation_types = excluded.renovation_types,
                rooms = excluded.rooms,
                pets_allowed = excluded.pets_allowed,
                no_commission = excluded.no_commission,
                commission_max_percent = excluded.commission_max_percent,
                tolerance_percent = excluded.tolerance_percent,
                initial_listings_count = excluded.initial_listings_count,
                is_active = excluded.is_active
            """,
            (
                f.user_id,
                f.city,
                f.district,
                f.metro,
                f.price_min,
                f.price_max,
                f.area_min,
                f.kitchen_area_min,
                json.dumps(f.renovation_types),
                json.dumps(f.rooms),
                int(f.pets_allowed),
                0 if f.commission_max_percent < 100 else 1,  # no_commission for backward compat
                f.commission_max_percent,
                f.tolerance_percent,
                f.initial_listings_count,
                int(f.is_active),
            ),
        )
        await self.db.commit()

    async def set_active(self, user_id: int, *, active: bool) -> None:
        """Включает или выключает мониторинг для пользователя."""
        await self.db.execute(
            "UPDATE user_filters SET is_active = ? WHERE user_id = ?",
            (int(active), user_id),
        )
        await self.db.commit()

    async def get_active_filters(self) -> Sequence[UserFilter]:
        """Возвращает фильтры всех пользователей с активным мониторингом."""
        cursor = await self.db.execute(
            "SELECT * FROM user_filters WHERE is_active = 1"
        )
        rows = await cursor.fetchall()
        return [_row_to_filter(row) for row in rows]

    # ── Просмотренные объявления ───────────────────────────────────

    async def is_seen(self, source: str, listing_id: int, user_id: int) -> bool:
        """Проверяет, было ли объявление уже отправлено пользователю."""
        cursor = await self.db.execute(
            "SELECT 1 FROM seen_listings WHERE source = ? AND listing_id = ? AND user_id = ?",
            (source, listing_id, user_id),
        )
        return await cursor.fetchone() is not None

    async def mark_seen(self, source: str, listing_id: int, user_id: int) -> None:
        """Помечает объявление как отправленное пользователю."""
        await self.db.execute(
            "INSERT OR IGNORE INTO seen_listings (source, listing_id, user_id) VALUES (?, ?, ?)",
            (source, listing_id, user_id),
        )
        await self.db.commit()

    async def cleanup_old(self, days: int = 30) -> None:
        """Удаляет записи старше N дней для экономии места."""
        await self.db.execute(
            "DELETE FROM seen_listings WHERE sent_at < datetime('now', ?)",
            (f"-{days} days",),
        )
        await self.db.commit()


def _row_to_filter(row: aiosqlite.Row) -> UserFilter:
    return UserFilter(
        user_id=row["user_id"],
        city=row["city"],
        district=row["district"],
        metro=row["metro"],
        price_min=row["price_min"],
        price_max=row["price_max"],
        area_min=row["area_min"],
        kitchen_area_min=row["kitchen_area_min"],
        renovation_types=json.loads(row["renovation_types"]),
        rooms=json.loads(row["rooms"]),
        pets_allowed=bool(row["pets_allowed"]),
        commission_max_percent=int(row["commission_max_percent"]) if "commission_max_percent" in row.keys() else (0 if row["no_commission"] else 100),
        tolerance_percent=int(row["tolerance_percent"]),
        initial_listings_count=int(row["initial_listings_count"]),
        is_active=bool(row["is_active"]),
    )
