"""aiohttp-роуты для Telegram Mini App (дашборд)."""

from __future__ import annotations

import logging
from pathlib import Path

from aiohttp import web

from src.data.cities import get_cities_display
from src.parser.models import RenovationType, UserFilter
from src.webapp.validation import validate_init_data

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).resolve().parent / "static"


def _commission_label(commission_max_percent: int) -> str:
    if commission_max_percent == 0:
        return "Только без комиссии"
    if commission_max_percent >= 100:
        return "Не важно"
    return f"До {commission_max_percent}%"


def _price_range_text(price_min: int, price_max: int) -> str:
    if price_min and price_max:
        return f"{price_min:,} – {price_max:,} ₽".replace(",", " ")
    if price_max:
        return f"до {price_max:,} ₽".replace(",", " ")
    if price_min:
        return f"от {price_min:,} ₽".replace(",", " ")
    return "Любая"


def _filter_summary(f: UserFilter) -> str:
    """Строит текстовое описание фильтров из UserFilter."""
    lines: list[str] = []
    lines.append(f"Города: {get_cities_display(f.cities)}")
    if f.rooms:
        lines.append(f"Комнаты: {', '.join(str(r) for r in sorted(f.rooms))}")
    else:
        lines.append("Комнаты: Любые")
    lines.append(f"Цена: {_price_range_text(f.price_min, f.price_max)}")
    lines.append(f"Площадь: {'от ' + str(f.area_min) + ' м²' if f.area_min else 'Не важно'}")
    lines.append(f"Кухня: {'от ' + str(f.kitchen_area_min) + ' м²' if f.kitchen_area_min else 'Не важно'}")
    if f.renovation_types:
        names = ", ".join(RenovationType.label(r) for r in f.renovation_types)
        lines.append(f"Ремонт: {names}")
    else:
        lines.append("Ремонт: Любой")
    lines.append(f"Животные: {'Скрывать с запретом' if f.pets_allowed else 'Показывать все'}")
    lines.append(f"Комиссия: {_commission_label(f.commission_max_percent)}")
    lines.append(f"Допуск: {f.tolerance_percent}%" if f.tolerance_percent else "Допуск: Отключён")
    return "\n".join(lines)


async def handle_index(_request: web.Request) -> web.Response:
    """Отдаёт index.html Mini App."""
    path = STATIC_DIR / "index.html"
    if not path.exists():
        raise web.HTTPNotFound()
    return web.FileResponse(path)


async def handle_dashboard(request: web.Request) -> web.Response:
    """API дашборда: статус мониторинга и сводка фильтров. Только для администратора."""
    init_data = request.query.get("init_data")
    if not init_data:
        raise web.HTTPBadRequest(text='Missing "init_data"')

    config = request.app["config"]
    validated = validate_init_data(init_data, config.bot_token)
    if not validated:
        raise web.HTTPForbidden()

    user = validated.get("user")
    if not user or "id" not in user:
        raise web.HTTPForbidden()

    user_id = int(user["id"])
    if user_id != config.admin_user_id:
        raise web.HTTPForbidden()

    db = request.app["db"]
    user_filter = await db.get_filter(user_id)

    if user_filter is None:
        data = {
            "has_filter": False,
            "is_active": False,
            "filter_summary": "",
        }
    else:
        data = {
            "has_filter": True,
            "is_active": user_filter.is_active,
            "filter_summary": _filter_summary(user_filter),
        }

    return web.json_response(data)


def create_app(db: object, config: object) -> web.Application:
    """Создаёт aiohttp Application с роутами."""
    app = web.Application()
    app["db"] = db
    app["config"] = config
    app.router.add_get("/", handle_index)
    app.router.add_get("/api/dashboard", handle_dashboard)
    return app
