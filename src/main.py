"""Точка входа: запуск Telegram-бота и планировщика мониторинга."""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from src.bot.handlers import router
from src.config import config
from src.scheduler.monitor import check_new_listings
from src.storage.database import Database

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def run() -> None:
    """Инициализирует и запускает бота вместе с планировщиком."""
    db = Database(config.db_path)
    await db.connect()

    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode="HTML"),
    )

    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    dp["db"] = db

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        check_new_listings,
        "interval",
        minutes=config.check_interval_minutes,
        args=[bot, db],
        id="rental_monitor",
        replace_existing=True,
    )
    scheduler.start()
    logger.info(
        "Планировщик запущен: проверка каждые %d мин.",
        config.check_interval_minutes,
    )

    try:
        logger.info("Бот запущен")
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown()
        await db.close()
        await bot.session.close()


def main() -> None:
    """Точка входа для запуска из CLI."""
    asyncio.run(run())


if __name__ == "__main__":
    main()
