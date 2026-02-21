"""Точка входа: запуск Telegram-бота и планировщика мониторинга."""

from __future__ import annotations

import asyncio
import logging

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from src.bot.handlers import router
from src.config import config
from src.scheduler.monitor import check_new_listings
from src.storage.database import Database
from src.webapp.routes import create_app

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

    webapp_runner: web.AppRunner | None = None
    if config.webapp_url:
        webapp = create_app(db=db, config=config)
        webapp_runner = web.AppRunner(webapp)
        await webapp_runner.setup()
        site = web.TCPSite(webapp_runner, config.webapp_host, config.webapp_port)
        await site.start()
        logger.info("Mini App сервер запущен на %s:%d", config.webapp_host, config.webapp_port)

    try:
        logger.info("Бот запущен")
        await dp.start_polling(bot)
    finally:
        if webapp_runner:
            await webapp_runner.cleanup()
        scheduler.shutdown()
        await db.close()
        await bot.session.close()


def main() -> None:
    """Точка входа для запуска из CLI."""
    asyncio.run(run())


if __name__ == "__main__":
    main()
