"""Периодическая задача мониторинга: парсинг всех площадок, фильтрация, отправка новых объявлений."""

from __future__ import annotations

import logging
from typing import List

from aiogram import Bot
from aiogram.types import InputMediaPhoto

from src.bot.formatter import format_listing
from src.parser.avito import search_listings as avito_search
from src.parser.cian import search_listings as cian_search
from src.parser.models import Listing, UserFilter
from src.parser.yandex_realty import search_listings as yandex_search
from src.storage.database import Database

logger = logging.getLogger(__name__)

MAX_PHOTOS_PER_LISTING = 4


async def check_new_listings(bot: Bot, db: Database) -> None:
    """Проверяет новые объявления для всех пользователей с активным мониторингом."""
    active_filters = await db.get_active_filters()

    if not active_filters:
        logger.debug("Нет активных фильтров — пропускаем проверку")
        return

    logger.info("Проверка объявлений для %d пользователей", len(active_filters))

    for user_filter in active_filters:
        try:
            await _process_user(bot, db, user_filter)
        except Exception:
            logger.exception(
                "Ошибка при обработке пользователя %d", user_filter.user_id
            )


async def _process_user(bot: Bot, db: Database, user_filter: UserFilter) -> None:
    """Парсит все площадки, фильтрует и отправляет новые объявления одному пользователю."""
    listings = await _aggregate_listings(user_filter)
    sent_count = 0

    for listing in listings:
        if await db.is_seen(listing.source.value, listing.listing_id, user_filter.user_id):
            continue

        if not user_filter.matches(listing):
            continue

        try:
            await _send_listing(bot, user_filter.user_id, listing)
            await db.mark_seen(listing.source.value, listing.listing_id, user_filter.user_id)
            sent_count += 1
        except Exception:
            logger.exception(
                "Ошибка при отправке объявления %s:%d пользователю %d",
                listing.source.value,
                listing.listing_id,
                user_filter.user_id,
            )

    if sent_count:
        logger.info(
            "Отправлено %d новых объявлений пользователю %d",
            sent_count,
            user_filter.user_id,
        )


async def _aggregate_listings(user_filter: UserFilter) -> List[Listing]:
    """Собирает объявления со всех площадок."""
    all_listings: List[Listing] = []

    for name, search_fn in [
        ("ЦИАН", cian_search),
        ("Авито", avito_search),
        ("Яндекс", yandex_search),
    ]:
        try:
            results = await search_fn(user_filter)
            all_listings.extend(results)
            logger.info("%s: получено %d объявлений", name, len(results))
        except Exception:
            logger.exception("Ошибка при парсинге %s", name)

    return all_listings


async def _send_listing(bot: Bot, user_id: int, listing: Listing) -> None:
    """Отправляет объявление пользователю: фото + текст."""
    text = format_listing(listing)

    if listing.photos:
        photos = listing.photos[:MAX_PHOTOS_PER_LISTING]
        media = [
            InputMediaPhoto(
                media=url,
                caption=text if i == 0 else None,
                parse_mode="HTML" if i == 0 else None,
            )
            for i, url in enumerate(photos)
        ]
        await bot.send_media_group(chat_id=user_id, media=media)
    else:
        await bot.send_message(
            chat_id=user_id,
            text=text,
            parse_mode="HTML",
            disable_web_page_preview=False,
        )
