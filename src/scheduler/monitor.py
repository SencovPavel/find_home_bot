"""Периодическая задача мониторинга: парсинг ЦИАН, фильтрация, отправка новых объявлений."""

from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.types import InputMediaPhoto

from src.bot.formatter import format_listing
from src.parser.cian import search_listings
from src.parser.models import Listing, UserFilter
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
    """Парсит, фильтрует и отправляет новые объявления одному пользователю."""
    listings = await search_listings(user_filter)
    sent_count = 0

    for listing in listings:
        if await db.is_seen(listing.cian_id, user_filter.user_id):
            continue

        if not user_filter.matches(listing):
            continue

        try:
            await _send_listing(bot, user_filter.user_id, listing)
            await db.mark_seen(listing.cian_id, user_filter.user_id)
            sent_count += 1
        except Exception:
            logger.exception(
                "Ошибка при отправке объявления %d пользователю %d",
                listing.cian_id,
                user_filter.user_id,
            )

    if sent_count:
        logger.info(
            "Отправлено %d новых объявлений пользователю %d",
            sent_count,
            user_filter.user_id,
        )


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
