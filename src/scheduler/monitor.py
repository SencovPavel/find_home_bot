"""Периодическая задача мониторинга: парсинг всех площадок, фильтрация, отправка новых объявлений."""

from __future__ import annotations

import logging
from typing import List, Optional

from aiogram import Bot
from aiogram.types import InputMediaPhoto

from src.bot.formatter import format_empty_listings_message, format_listing, format_listing_approx
from src.parser.avito import search_listings as avito_search
from src.parser.cian import search_listings as cian_search

from src.parser.models import Listing, UserFilter
from src.parser.yandex_realty import search_listings as yandex_search
from src.config import Config
from src.storage.database import Database

logger = logging.getLogger(__name__)

MAX_PHOTOS_PER_LISTING = 4


async def _resolve_destination(
    db: Database,
    user_filter: UserFilter,
    config: Config,
) -> tuple[int, Optional[int]]:
    """Возвращает (chat_id, message_thread_id) для отправки. thread_id=None — личка."""
    if user_filter.user_id != config.admin_user_id:
        return (user_filter.user_id, None)
    topic_config = await db.get_group_topic_config()
    if topic_config is not None:
        return topic_config
    if config.group_chat_id is not None and config.group_topic_id is not None:
        return (config.group_chat_id, config.group_topic_id)
    return (user_filter.user_id, None)


async def check_new_listings(bot: Bot, db: Database, config: Config) -> None:
    """Проверяет новые объявления для всех пользователей с активным мониторингом."""
    active_filters = await db.get_active_filters()

    if not active_filters:
        logger.debug("Нет активных фильтров — пропускаем проверку")
        return

    logger.info("Проверка объявлений для %d пользователей", len(active_filters))

    for user_filter in active_filters:
        try:
            await _process_user(bot, db, user_filter, config)
        except Exception:
            logger.exception(
                "Ошибка при обработке пользователя %d", user_filter.user_id
            )


async def _send_empty_listings_notification(
    bot: Bot,
    chat_id: int,
    *,
    message_thread_id: Optional[int] = None,
) -> None:
    """Отправляет уведомление об отсутствии объявлений по фильтрам."""
    text = format_empty_listings_message()
    kwargs: dict = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if message_thread_id is not None:
        kwargs["message_thread_id"] = message_thread_id
    await bot.send_message(**kwargs)


async def _process_user(
    bot: Bot, db: Database, user_filter: UserFilter, config: Config
) -> None:
    """Парсит все площадки, фильтрует и отправляет новые объявления одному пользователю."""
    chat_id, message_thread_id = await _resolve_destination(db, user_filter, config)

    listings = await _aggregate_listings(user_filter)
    sent_count = 0
    approx_count = 0
    total_matching = 0

    for listing in listings:
        matches_strict = user_filter.matches(listing)
        matches_approx = user_filter.matches_approx(listing)
        if matches_strict or matches_approx is not None:
            total_matching += 1

        if await db.is_seen(listing.source.value, listing.listing_id, user_filter.user_id):
            continue

        if matches_strict:
            try:
                await _send_listing(
                    bot, chat_id, listing, message_thread_id=message_thread_id
                )
                await db.mark_seen(listing.source.value, listing.listing_id, user_filter.user_id)
                sent_count += 1
            except Exception:
                logger.exception(
                    "Ошибка при отправке объявления %s:%s пользователю %d",
                    listing.source.value,
                    listing.listing_id,
                    user_filter.user_id,
                )
            continue

        deviations = matches_approx
        if deviations is not None:
            try:
                await _send_listing(
                    bot,
                    chat_id,
                    listing,
                    message_thread_id=message_thread_id,
                    deviations=deviations,
                )
                await db.mark_seen(listing.source.value, listing.listing_id, user_filter.user_id)
                approx_count += 1
            except Exception:
                logger.exception(
                    "Ошибка при отправке приблизительного объявления %s:%s пользователю %d",
                    listing.source.value,
                    listing.listing_id,
                    user_filter.user_id,
                )

    if sent_count or approx_count:
        logger.info(
            "Пользователь %d: отправлено %d точных, %d приблизительных",
            user_filter.user_id,
            sent_count,
            approx_count,
        )
    elif total_matching == 0 and user_filter.empty_notified_at is None:
        try:
            await _send_empty_listings_notification(
                bot, chat_id, message_thread_id=message_thread_id
            )
            await db.mark_empty_notified(user_filter.user_id)
        except Exception:
            logger.exception(
                "Ошибка при отправке уведомления об отсутствии объявлений пользователю %d",
                user_filter.user_id,
            )


async def _aggregate_listings(
    user_filter: UserFilter,
    pages: int = 2,
) -> List[Listing]:
    """Собирает объявления со всех площадок."""
    all_listings: List[Listing] = []

    for name, search_fn in [
        ("ЦИАН", cian_search),
        ("Авито", avito_search),
        ("Яндекс", yandex_search),
    ]:
        try:
            results = await search_fn(user_filter, pages=pages)
            all_listings.extend(results)
            logger.info("%s: получено %d объявлений", name, len(results))
        except Exception:
            logger.exception("Ошибка при парсинге %s", name)

    return all_listings


async def send_initial_listings(
    bot: Bot,
    db: Database,
    user_filter: UserFilter,
    config: Config,
) -> int:
    """Отправляет до initial_listings_count объявлений при старте мониторинга.

    Собирает объявления (1 страница), фильтрует, сортирует (strict, затем approx),
    отправляет до N штук и помечает как просмотренные.
    """
    limit = user_filter.initial_listings_count
    if limit <= 0:
        return 0

    chat_id, message_thread_id = await _resolve_destination(db, user_filter, config)

    try:
        listings = await _aggregate_listings(user_filter, pages=1)
    except Exception:
        logger.exception(
            "Ошибка при сборе объявлений для начальной выдачи пользователю %d",
            user_filter.user_id,
        )
        return 0

    strict: List[tuple[Listing, Optional[List[str]]]] = []
    approx: List[tuple[Listing, Optional[List[str]]]] = []
    matched_but_seen = False

    for listing in listings:
        matches_strict = user_filter.matches(listing)
        matches_approx = user_filter.matches_approx(listing)
        is_seen = await db.is_seen(
            listing.source.value, listing.listing_id, user_filter.user_id
        )
        if is_seen:
            if matches_strict or matches_approx is not None:
                matched_but_seen = True
            continue
        if matches_strict:
            strict.append((listing, None))
        elif matches_approx is not None:
            approx.append((listing, matches_approx))

    to_send = strict + approx
    sent = 0

    for listing, deviations in to_send[:limit]:
        try:
            await _send_listing(
                bot,
                chat_id,
                listing,
                message_thread_id=message_thread_id,
                deviations=deviations,
            )
            await db.mark_seen(
                listing.source.value, listing.listing_id, user_filter.user_id
            )
            sent += 1
        except Exception:
            logger.exception(
                "Ошибка при отправке начального объявления %s:%s пользователю %d",
                listing.source.value,
                listing.listing_id,
                user_filter.user_id,
            )

    if sent:
        logger.info(
            "Пользователь %d: отправлено %d объявлений при старте",
            user_filter.user_id,
            sent,
        )
    elif not matched_but_seen:
        try:
            await _send_empty_listings_notification(
                bot, chat_id, message_thread_id=message_thread_id
            )
            await db.mark_empty_notified(user_filter.user_id)
        except Exception:
            logger.exception(
                "Ошибка при отправке уведомления об отсутствии объявлений пользователю %d",
                user_filter.user_id,
            )
    return sent


async def _send_listing(
    bot: Bot,
    chat_id: int,
    listing: Listing,
    *,
    message_thread_id: Optional[int] = None,
    deviations: Optional[List[str]] = None,
) -> None:
    """Отправляет объявление: фото + текст в chat_id, опционально в тему."""
    text = format_listing_approx(listing, deviations) if deviations else format_listing(listing)

    send_kwargs: dict = {"chat_id": chat_id}
    if message_thread_id is not None:
        send_kwargs["message_thread_id"] = message_thread_id

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
        await bot.send_media_group(media=media, **send_kwargs)
    else:
        await bot.send_message(
            text=text,
            parse_mode="HTML",
            disable_web_page_preview=False,
            **send_kwargs,
        )
