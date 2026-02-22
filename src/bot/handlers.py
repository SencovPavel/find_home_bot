"""Обработчики команд и callback-запросов Telegram-бота."""

from __future__ import annotations

import asyncio
import difflib
import logging
import time
from typing import TYPE_CHECKING

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from src.bot.keyboards import (
    MAX_CITIES_SELECT,
    RENOVATION_OPTIONS,
    area_keyboard,
    city_millioners_keyboard,
    city_search_results_keyboard,
    commands_inline_keyboard,
    commands_reply_keyboard,
    commission_keyboard,
    confirm_keyboard,
    edit_filter_menu_keyboard,
    edit_filter_single_button_keyboard,
    initial_listings_keyboard,
    kitchen_keyboard,
    pets_keyboard,
    price_keyboard,
    renovation_keyboard,
    rooms_keyboard,
    tolerance_keyboard,
)
from src.config import config
from src.data.cities import get_city_by_id, get_cities_display, get_city_name, search_cities
from src.parser.models import RenovationType, UserFilter
from src.scheduler.monitor import send_initial_listings

if TYPE_CHECKING:
    from src.storage.database import Database

logger = logging.getLogger(__name__)

router = Router()

MAX_PRICE_RUB = 10_000_000
RATE_LIMIT_SECONDS = 0.7
_LAST_REQUEST_TS_BY_USER: dict[int, float] = {}

TOTAL_STEPS = 10


class SearchWizard(StatesGroup):
    """Состояния пошагового мастера настройки фильтров."""

    city = State()
    rooms = State()
    price = State()
    price_custom_min = State()
    price_custom_max = State()
    area = State()
    kitchen = State()
    renovation = State()
    pets = State()
    commission = State()
    commission_text = State()
    tolerance = State()
    tolerance_text = State()
    initial_listings = State()
    initial_listings_text = State()
    confirm = State()


# ── /start ─────────────────────────────────────────────────────────

@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    """Приветствие и инструкция."""
    if await _is_rate_limited_message(message):
        return
    await message.answer(
        "<b>Привет! Я бот для поиска квартир в аренду.</b>\n\n"
        "Я мониторю ЦИАН, Авито и Яндекс Недвижимость и отправляю подходящие объявления.\n\n"
        "<b>Команды:</b>\n"
        "/search — настроить фильтры и начать поиск\n"
        "/filters — посмотреть текущие фильтры\n"
        "/pause — приостановить мониторинг\n"
        "/resume — возобновить мониторинг\n"
        "/help — список всех команд",
        reply_markup=commands_reply_keyboard(),
        parse_mode="HTML",
    )
    user_id = message.from_user.id if message.from_user else 0  # type: ignore[union-attr]
    await message.answer(
        "Быстрые действия:",
        reply_markup=commands_inline_keyboard(
            webapp_url=config.webapp_url,
            user_id=user_id,
            admin_user_id=config.admin_user_id,
        ),
    )


# ── /help ──────────────────────────────────────────────────────────

@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    """Список всех доступных команд."""
    if await _is_rate_limited_message(message):
        return
    await message.answer(
        "<b>Доступные команды:</b>\n\n"
        "/start — приветствие и инструкция\n"
        "/search — настроить фильтры и начать поиск\n"
        "/filters — посмотреть текущие фильтры\n"
        "/pause — приостановить мониторинг\n"
        "/resume — возобновить мониторинг\n"
        "/help — этот список команд",
        parse_mode="HTML",
    )


# ── /search — запуск wizard ────────────────────────────────────────

async def _start_search_wizard(message: Message, state: FSMContext) -> None:
    """Старт пошаговой настройки фильтров (общая логика для команды и callback)."""
    await state.clear()
    await state.update_data(
        cities=[],
        rooms=[],
        renovation_types=[],
    )
    await message.answer(
        f"🏙 <b>Шаг 1/{TOTAL_STEPS}:</b> Выберите город из списка или введите название",
        reply_markup=city_millioners_keyboard(),
        parse_mode="HTML",
    )
    await state.set_state(SearchWizard.city)


@router.message(Command("search"))
async def cmd_search(
    message: Message,
    state: FSMContext,
    *,
    skip_rate_limit: bool = False,
) -> None:
    """Начало пошаговой настройки фильтров."""
    if not skip_rate_limit and await _is_rate_limited_message(message):
        return
    await _start_search_wizard(message, state)


# ── Город ──────────────────────────────────────────────────────────

@router.message(SearchWizard.city)
async def on_city_text(message: Message, state: FSMContext) -> None:
    """Текстовый поиск города по введённому названию."""
    if await _is_rate_limited_message(message):
        return
    query = (message.text or "").strip()
    if not query:
        await message.answer("Пожалуйста, введите название города.")
        return

    found = search_cities(query)
    if not found:
        await message.answer(
            "Город не найден. Попробуйте ввести название ещё раз.",
        )
        return

    data = await state.get_data()
    selected = data.get("cities", [])

    await message.answer(
        f"🏙 Найдено городов: <b>{len(found)}</b>. Выберите из списка или введите «Готово» после выбора:",
        reply_markup=city_search_results_keyboard(found, selected),
        parse_mode="HTML",
    )


@router.callback_query(SearchWizard.city, F.data.startswith("city:"))
async def on_city(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
    if await _is_rate_limited_callback(callback):
        return
    parts = _parse_callback_parts(callback.data, "city", expected_parts=2)
    if parts is None:
        await _reject_bad_callback(callback)
        return
    data = await state.get_data()
    cities: list[int] = data.get("cities", [])

    if parts[1] == "done":
        if not cities:
            await callback.answer("Выберите хотя бы один город", show_alert=True)
            return
        if edit_field := data.get("edit_filter"):
            await _save_edit_filter_and_show(callback, state, db, callback.from_user.id, edit_field)
            await callback.answer()
            return
        cities_text = get_cities_display(cities)
        await callback.message.edit_text(  # type: ignore[union-attr]
            f"🏙 Города: <b>{cities_text}</b>\n\n"
            f"🚪 <b>Шаг 2/{TOTAL_STEPS}:</b> Выберите количество комнат",
            reply_markup=rooms_keyboard(),
            parse_mode="HTML",
        )
        await state.set_state(SearchWizard.rooms)
        await callback.answer()
        return

    city_id = _parse_int_in_range(parts[1], minimum=1, maximum=10_000)
    if city_id is None:
        await _reject_bad_callback(callback)
        return
    city = get_city_by_id(city_id)
    if city is None:
        await _reject_bad_callback(callback, text="Город не найден.")
        return

    if city_id in cities:
        cities = [c for c in cities if c != city_id]
    else:
        if len(cities) >= MAX_CITIES_SELECT:
            await callback.answer(f"Максимум {MAX_CITIES_SELECT} городов", show_alert=True)
            return
        cities = sorted(cities + [city_id])
    await state.update_data(cities=cities)

    cities_text = get_cities_display(cities) if cities else "Не выбрано"
    await callback.message.edit_text(  # type: ignore[union-attr]
        f"🏙 <b>Шаг 1/{TOTAL_STEPS}:</b> Выберите города\n\n"
        f"Выбрано: <b>{cities_text}</b>\n"
        "Добавьте ещё или нажмите Готово:",
        reply_markup=city_millioners_keyboard(cities),
        parse_mode="HTML",
    )
    await callback.answer()


# ── Комнаты (мульти-выбор) ─────────────────────────────────────────

@router.callback_query(SearchWizard.rooms, F.data.startswith("rooms:"))
async def on_rooms(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
    if await _is_rate_limited_callback(callback):
        return
    parts = _parse_callback_parts(callback.data, "rooms", expected_parts=2)
    if parts is None:
        await _reject_bad_callback(callback)
        return
    value = parts[1]

    if value == "done":
        data = await state.get_data()
        if edit_field := data.get("edit_filter"):
            await _save_edit_filter_and_show(callback, state, db, callback.from_user.id, edit_field)
            await callback.answer()
            return
        rooms = data.get("rooms", [])
        rooms_text = ", ".join(f"{r}-комн." for r in sorted(rooms)) if rooms else "Любые"
        await callback.message.edit_text(  # type: ignore[union-attr]
            f"🚪 Комнаты: <b>{rooms_text}</b>\n\n"
            f"💰 <b>Шаг 3/{TOTAL_STEPS}:</b> Выберите ценовой диапазон",
            reply_markup=price_keyboard(),
            parse_mode="HTML",
        )
        await state.set_state(SearchWizard.price)
    else:
        room_num = _parse_int_in_range(value, minimum=0, maximum=9)
        if room_num is None:
            await _reject_bad_callback(callback)
            return
        data = await state.get_data()
        rooms: list[int] = data.get("rooms", [])
        if room_num in rooms:
            rooms.remove(room_num)
        else:
            rooms.append(room_num)
        await state.update_data(rooms=rooms)
        await callback.message.edit_reply_markup(  # type: ignore[union-attr]
            reply_markup=rooms_keyboard(rooms),
        )

    await callback.answer()


# ── Цена ───────────────────────────────────────────────────────────

@router.callback_query(SearchWizard.price, F.data.startswith("price:"))
async def on_price(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
    if await _is_rate_limited_callback(callback):
        return
    parts = _parse_callback_parts(callback.data, "price", minimum_parts=2, maximum_parts=3)
    if parts is None:
        await _reject_bad_callback(callback)
        return

    if parts[1] == "custom":
        if len(parts) != 2:
            await _reject_bad_callback(callback)
            return
        await callback.message.edit_text(  # type: ignore[union-attr]
            "💰 Введите <b>минимальную</b> цену (руб/мес).\n"
            "Отправьте <b>0</b>, если без нижней границы.",
            parse_mode="HTML",
        )
        await state.set_state(SearchWizard.price_custom_min)
    else:
        if len(parts) != 3:
            await _reject_bad_callback(callback)
            return
        price_min = _parse_int_in_range(parts[1], minimum=0, maximum=MAX_PRICE_RUB)
        price_max = _parse_int_in_range(parts[2], minimum=0, maximum=MAX_PRICE_RUB)
        if price_min is None or price_max is None:
            await _reject_bad_callback(callback)
            return
        if price_max and price_min > price_max:
            await _reject_bad_callback(callback, text="Некорректный диапазон цены.")
            return
        await state.update_data(price_min=price_min, price_max=price_max)
        data = await state.get_data()
        if edit_field := data.get("edit_filter"):
            await _save_edit_filter_and_show(callback, state, db, callback.from_user.id, edit_field)
            await callback.answer()
            return
        await _show_area_step(callback, state, price_min, price_max)

    await callback.answer()


@router.message(SearchWizard.price_custom_min)
async def on_price_custom_min(message: Message, state: FSMContext) -> None:
    if await _is_rate_limited_message(message):
        return
    price_min = _parse_price_input(message.text)
    if price_min is None:
        await message.answer("Пожалуйста, введите число.")
        return

    await state.update_data(price_min=price_min)
    await message.answer(
        "💰 Введите <b>максимальную</b> цену (руб/мес).\n"
        "Отправьте <b>0</b>, если без верхней границы.",
        parse_mode="HTML",
    )
    await state.set_state(SearchWizard.price_custom_max)


@router.message(SearchWizard.price_custom_max)
async def on_price_custom_max(message: Message, state: FSMContext, db: Database) -> None:
    if await _is_rate_limited_message(message):
        return
    price_max = _parse_price_input(message.text)
    if price_max is None:
        await message.answer("Пожалуйста, введите число.")
        return

    data = await state.get_data()
    price_min = data.get("price_min", 0)
    if not isinstance(price_min, int):
        await message.answer("Ошибка данных фильтра. Начните заново: /search")
        await state.clear()
        return
    if price_max and price_min > price_max:
        await message.answer("Максимальная цена должна быть больше или равна минимальной.")
        return
    await state.update_data(price_max=price_max)
    if edit_field := data.get("edit_filter"):
        await _save_edit_filter_and_show(message, state, db, message.from_user.id, edit_field)  # type: ignore[union-attr]
        return
    await message.answer(
        f"💰 Цена: <b>{_price_range_text(price_min, price_max)}</b>\n\n"
        f"📐 <b>Шаг 4/{TOTAL_STEPS}:</b> Минимальная общая площадь",
        reply_markup=area_keyboard(),
        parse_mode="HTML",
    )
    await state.set_state(SearchWizard.area)


async def _show_area_step(
    callback: CallbackQuery, state: FSMContext, price_min: int, price_max: int
) -> None:
    await callback.message.edit_text(  # type: ignore[union-attr]
        f"💰 Цена: <b>{_price_range_text(price_min, price_max)}</b>\n\n"
        f"📐 <b>Шаг 4/{TOTAL_STEPS}:</b> Минимальная общая площадь",
        reply_markup=area_keyboard(),
        parse_mode="HTML",
    )
    await state.set_state(SearchWizard.area)


# ── Площадь ────────────────────────────────────────────────────────

@router.callback_query(SearchWizard.area, F.data.startswith("area:"))
async def on_area(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
    if await _is_rate_limited_callback(callback):
        return
    parts = _parse_callback_parts(callback.data, "area", expected_parts=2)
    if parts is None:
        await _reject_bad_callback(callback)
        return
    area = _parse_int_in_range(parts[1], minimum=0, maximum=1_000)
    if area is None:
        await _reject_bad_callback(callback)
        return
    await state.update_data(area_min=area)

    data = await state.get_data()
    if edit_field := data.get("edit_filter"):
        await _save_edit_filter_and_show(callback, state, db, callback.from_user.id, edit_field)
        await callback.answer()
        return

    area_text = f"от {area} м²" if area else "Не важно"
    await callback.message.edit_text(  # type: ignore[union-attr]
        f"📐 Площадь: <b>{area_text}</b>\n\n"
        f"🍳 <b>Шаг 5/{TOTAL_STEPS}:</b> Минимальная площадь кухни",
        reply_markup=kitchen_keyboard(),
        parse_mode="HTML",
    )
    await state.set_state(SearchWizard.kitchen)
    await callback.answer()


# ── Кухня ──────────────────────────────────────────────────────────

@router.callback_query(SearchWizard.kitchen, F.data.startswith("kitchen:"))
async def on_kitchen(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
    if await _is_rate_limited_callback(callback):
        return
    parts = _parse_callback_parts(callback.data, "kitchen", expected_parts=2)
    if parts is None:
        await _reject_bad_callback(callback)
        return
    kitchen = _parse_int_in_range(parts[1], minimum=0, maximum=1_000)
    if kitchen is None:
        await _reject_bad_callback(callback)
        return
    await state.update_data(kitchen_area_min=kitchen)

    data = await state.get_data()
    if edit_field := data.get("edit_filter"):
        await _save_edit_filter_and_show(callback, state, db, callback.from_user.id, edit_field)
        await callback.answer()
        return

    kitchen_text = f"от {kitchen} м²" if kitchen else "Не важно"
    await callback.message.edit_text(  # type: ignore[union-attr]
        f"🍳 Кухня: <b>{kitchen_text}</b>\n\n"
        f"🔧 <b>Шаг 6/{TOTAL_STEPS}:</b> Допустимый тип ремонта",
        reply_markup=renovation_keyboard(),
        parse_mode="HTML",
    )
    await state.set_state(SearchWizard.renovation)
    await callback.answer()


# ── Ремонт (мульти-выбор) ─────────────────────────────────────────

@router.callback_query(SearchWizard.renovation, F.data.startswith("renovation:"))
async def on_renovation(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
    if await _is_rate_limited_callback(callback):
        return
    parts = _parse_callback_parts(callback.data, "renovation", expected_parts=2)
    if parts is None:
        await _reject_bad_callback(callback)
        return
    value = parts[1]

    if value == "any":
        await state.update_data(renovation_types=[])
        data = await state.get_data()
        if edit_field := data.get("edit_filter"):
            await _save_edit_filter_and_show(callback, state, db, callback.from_user.id, edit_field)
            await callback.answer()
            return
        await _show_pets_step(callback, state, [])
    elif value == "done":
        data = await state.get_data()
        if edit_field := data.get("edit_filter"):
            await _save_edit_filter_and_show(callback, state, db, callback.from_user.id, edit_field)
            await callback.answer()
            return
        selected = data.get("renovation_types", [])
        await _show_pets_step(callback, state, selected)
    else:
        if value not in RENOVATION_OPTIONS:
            await _reject_bad_callback(callback)
            return
        data = await state.get_data()
        selected: list[str] = data.get("renovation_types", [])
        if value in selected:
            selected.remove(value)
        else:
            selected.append(value)
        await state.update_data(renovation_types=selected)
        await callback.message.edit_reply_markup(  # type: ignore[union-attr]
            reply_markup=renovation_keyboard(selected),
        )

    await callback.answer()


async def _show_pets_step(
    callback: CallbackQuery, state: FSMContext, renovation_types: list[str]
) -> None:
    if renovation_types:
        names = ", ".join(RenovationType.label(r) for r in renovation_types)
    else:
        names = "Любой"

    await callback.message.edit_text(  # type: ignore[union-attr]
        f"🔧 Ремонт: <b>{names}</b>\n\n"
        f"🐾 <b>Шаг 7/{TOTAL_STEPS}:</b> Фильтр по животным",
        reply_markup=pets_keyboard(),
        parse_mode="HTML",
    )
    await state.set_state(SearchWizard.pets)


# ── Животные ───────────────────────────────────────────────────────

@router.callback_query(SearchWizard.pets, F.data.startswith("pets:"))
async def on_pets(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
    if await _is_rate_limited_callback(callback):
        return
    parts = _parse_callback_parts(callback.data, "pets", expected_parts=2)
    if parts is None:
        await _reject_bad_callback(callback)
        return
    if parts[1] not in {"0", "1"}:
        await _reject_bad_callback(callback)
        return
    pets_allowed = parts[1] == "1"
    await state.update_data(pets_allowed=pets_allowed)

    data = await state.get_data()
    if edit_field := data.get("edit_filter"):
        await _save_edit_filter_and_show(callback, state, db, callback.from_user.id, edit_field)
        await callback.answer()
        return

    pets_text = "Скрывать с запретом" if pets_allowed else "Показывать все"
    await callback.message.edit_text(  # type: ignore[union-attr]
        f"🐾 Животные: <b>{pets_text}</b>\n\n"
        f"💼 <b>Шаг 8/{TOTAL_STEPS}:</b> Фильтр по комиссии",
        reply_markup=commission_keyboard(),
        parse_mode="HTML",
    )
    await state.set_state(SearchWizard.commission)
    await callback.answer()


# ── Комиссия ───────────────────────────────────────────────────────

@router.callback_query(SearchWizard.commission, F.data.startswith("commission:"))
async def on_commission(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
    if await _is_rate_limited_callback(callback):
        return
    parts = _parse_callback_parts(callback.data, "commission", expected_parts=2)
    if parts is None:
        await _reject_bad_callback(callback)
        return

    if parts[1] == "custom":
        await callback.message.edit_text(  # type: ignore[union-attr]
            "💼 Введите допустимый максимум комиссии в процентах (от 0 до 99).\n"
            "0 — только без комиссии.",
            parse_mode="HTML",
        )
        await state.set_state(SearchWizard.commission_text)
        await callback.answer()
        return

    value = _parse_int_in_range(parts[1], minimum=0, maximum=100)
    if value is None:
        await _reject_bad_callback(callback)
        return
    await state.update_data(commission_max_percent=value)

    data = await state.get_data()
    if edit_field := data.get("edit_filter"):
        await _save_edit_filter_and_show(callback, state, db, callback.from_user.id, edit_field)
        await callback.answer()
        return

    comm_label = _commission_label(value)
    await callback.message.edit_text(  # type: ignore[union-attr]
        f"💼 Комиссия: <b>{comm_label}</b>\n\n"
        f"📊 <b>Шаг 9/{TOTAL_STEPS}:</b> Допуск для «почти подходящих» объявлений\n"
        "Если объявление чуть-чуть не попадает в критерии (цена, площадь), "
        "оно придёт с пометкой.",
        reply_markup=tolerance_keyboard(),
        parse_mode="HTML",
    )
    await state.set_state(SearchWizard.tolerance)
    await callback.answer()


@router.message(SearchWizard.commission_text)
async def on_commission_text(message: Message, state: FSMContext, db: Database) -> None:
    if await _is_rate_limited_message(message):
        return
    raw = (message.text or "").strip().replace("%", "")
    value = _parse_int_in_range(raw, minimum=0, maximum=99)
    if value is None:
        await message.answer("Введите число от 0 до 99.")
        return

    await state.update_data(commission_max_percent=value)
    data = await state.get_data()
    if edit_field := data.get("edit_filter"):
        await _save_edit_filter_and_show(message, state, db, message.from_user.id, edit_field)  # type: ignore[union-attr]
        return

    comm_label = _commission_label(value)
    await message.answer(
        f"💼 Комиссия: <b>{comm_label}</b>\n\n"
        f"📊 <b>Шаг 9/{TOTAL_STEPS}:</b> Допуск для «почти подходящих» объявлений\n"
        "Если объявление чуть-чуть не попадает в критерии (цена, площадь), "
        "оно придёт с пометкой.",
        reply_markup=tolerance_keyboard(),
        parse_mode="HTML",
    )
    await state.set_state(SearchWizard.tolerance)


# ── Допуск (tolerance) ─────────────────────────────────────────────

@router.callback_query(SearchWizard.tolerance, F.data.startswith("tolerance:"))
async def on_tolerance(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
    if await _is_rate_limited_callback(callback):
        return
    parts = _parse_callback_parts(callback.data, "tolerance", expected_parts=2)
    if parts is None:
        await _reject_bad_callback(callback)
        return

    if parts[1] == "custom":
        await callback.message.edit_text(  # type: ignore[union-attr]
            "📊 Введите допуск в процентах (от 1 до 50).\n"
            "Например, <b>15</b> — объявления с отклонением до 15% будут приходить с пометкой.",
            parse_mode="HTML",
        )
        await state.set_state(SearchWizard.tolerance_text)
        await callback.answer()
        return

    tolerance = _parse_int_in_range(parts[1], minimum=0, maximum=50)
    if tolerance is None:
        await _reject_bad_callback(callback)
        return
    await state.update_data(tolerance_percent=tolerance)
    data = await state.get_data()
    if edit_field := data.get("edit_filter"):
        await _save_edit_filter_and_show(callback, state, db, callback.from_user.id, edit_field)
        await callback.answer()
        return
    await _show_initial_listings_step(callback, state)
    await callback.answer()


@router.message(SearchWizard.tolerance_text)
async def on_tolerance_text(message: Message, state: FSMContext, db: Database) -> None:
    if await _is_rate_limited_message(message):
        return
    raw = (message.text or "").strip().replace("%", "")
    tolerance = _parse_int_in_range(raw, minimum=1, maximum=50)
    if tolerance is None:
        await message.answer("Введите число от 1 до 50.")
        return

    await state.update_data(tolerance_percent=tolerance)
    data = await state.get_data()
    if edit_field := data.get("edit_filter"):
        await _save_edit_filter_and_show(message, state, db, message.from_user.id, edit_field)  # type: ignore[union-attr]
        return
    await message.answer(
        f"📊 <b>Шаг {TOTAL_STEPS}/{TOTAL_STEPS}:</b> Сколько объявлений показать сразу при запуске?",
        reply_markup=initial_listings_keyboard(),
        parse_mode="HTML",
    )
    await state.set_state(SearchWizard.initial_listings)


@router.callback_query(SearchWizard.initial_listings, F.data.startswith("initial_listings:"))
async def on_initial_listings(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
    if await _is_rate_limited_callback(callback):
        return
    parts = _parse_callback_parts(callback.data, "initial_listings", expected_parts=2)
    if parts is None:
        await _reject_bad_callback(callback)
        return

    if parts[1] == "custom":
        await callback.message.edit_text(  # type: ignore[union-attr]
            "📋 Введите число объявлений (от 1 до 30).\n"
            "Столько подходящих объявлений будет отправлено сразу при запуске мониторинга.",
            parse_mode="HTML",
        )
        await state.set_state(SearchWizard.initial_listings_text)
        await callback.answer()
        return

    value = _parse_int_in_range(parts[1], minimum=0, maximum=30)
    if value is None:
        await _reject_bad_callback(callback)
        return
    await state.update_data(initial_listings_count=value)
    data = await state.get_data()
    if edit_field := data.get("edit_filter"):
        await _save_edit_filter_and_show(callback, state, db, callback.from_user.id, edit_field)
        await callback.answer()
        return
    await _show_confirm_step(callback, state)
    await callback.answer()


@router.message(SearchWizard.initial_listings_text)
async def on_initial_listings_text(message: Message, state: FSMContext, db: Database) -> None:
    if await _is_rate_limited_message(message):
        return
    raw = (message.text or "").strip()
    value = _parse_int_in_range(raw, minimum=1, maximum=30)
    if value is None:
        await message.answer("Введите число от 1 до 30.")
        return

    await state.update_data(initial_listings_count=value)
    data = await state.get_data()
    if edit_field := data.get("edit_filter"):
        await _save_edit_filter_and_show(message, state, db, message.from_user.id, edit_field)  # type: ignore[union-attr]
        return
    summary = _build_summary(data)
    await message.answer(
        f"<b>Ваши фильтры:</b>\n\n{summary}",
        reply_markup=confirm_keyboard(),
        parse_mode="HTML",
    )
    await state.set_state(SearchWizard.confirm)


async def _show_initial_listings_step(callback: CallbackQuery, state: FSMContext) -> None:
    """Показывает шаг выбора количества объявлений при старте."""
    await callback.message.edit_text(  # type: ignore[union-attr]
        f"📋 <b>Шаг {TOTAL_STEPS}/{TOTAL_STEPS}:</b> Сколько объявлений показать сразу при запуске?",
        reply_markup=initial_listings_keyboard(),
        parse_mode="HTML",
    )
    await state.set_state(SearchWizard.initial_listings)


async def _show_confirm_step(callback: CallbackQuery, state: FSMContext) -> None:
    """Показывает итоговую сводку фильтров и кнопки подтверждения."""
    data = await state.get_data()
    summary = _build_summary(data)
    await callback.message.edit_text(  # type: ignore[union-attr]
        f"<b>Ваши фильтры:</b>\n\n{summary}",
        reply_markup=confirm_keyboard(),
        parse_mode="HTML",
    )
    await state.set_state(SearchWizard.confirm)


# ── Кнопка «Назад» ──────────────────────────────────────────────────

@router.callback_query(
    StateFilter(
        SearchWizard.rooms,
        SearchWizard.price,
        SearchWizard.area,
        SearchWizard.kitchen,
        SearchWizard.renovation,
        SearchWizard.pets,
        SearchWizard.commission,
        SearchWizard.tolerance,
        SearchWizard.initial_listings,
        SearchWizard.confirm,
    ),
    F.data == "back",
)
async def on_back(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
    """Обработка кнопки «Назад»: возврат к предыдущему шагу или к /filters в режиме редактирования."""
    if await _is_rate_limited_callback(callback):
        return

    current = await state.get_state()
    data = await state.get_data()
    if data.get("edit_filter"):
        await state.clear()
        msg = callback.message
        if msg is not None:
            await _show_filters_view(msg, db=db, user_id=callback.from_user.id)
        await callback.answer()
        return
    msg = callback.message
    if msg is None:
        await callback.answer()
        return

    if current == SearchWizard.rooms.state:
        await state.set_state(SearchWizard.city)
        cities = data.get("cities", [])
        await msg.edit_text(
            f"🏙 <b>Шаг 1/{TOTAL_STEPS}:</b> Выберите города из списка или введите название",
            reply_markup=city_millioners_keyboard(cities),
            parse_mode="HTML",
        )
    elif current == SearchWizard.price.state:
        rooms = data.get("rooms", [])
        rooms_text = ", ".join(f"{r}-комн." for r in sorted(rooms)) if rooms else "Любые"
        cities = data.get("cities", [1])
        cities_text = get_cities_display(cities)
        await state.set_state(SearchWizard.rooms)
        await msg.edit_text(
            f"🏙 Города: <b>{cities_text}</b>\n\n"
            f"🚪 <b>Шаг 2/{TOTAL_STEPS}:</b> Выберите количество комнат",
            reply_markup=rooms_keyboard(rooms),
            parse_mode="HTML",
        )
    elif current == SearchWizard.area.state:
        rooms = data.get("rooms", [])
        rooms_text = ", ".join(f"{r}-комн." for r in sorted(rooms)) if rooms else "Любые"
        await state.set_state(SearchWizard.price)
        await msg.edit_text(
            f"🚪 Комнаты: <b>{rooms_text}</b>\n\n"
            f"💰 <b>Шаг 3/{TOTAL_STEPS}:</b> Выберите ценовой диапазон",
            reply_markup=price_keyboard(),
            parse_mode="HTML",
        )
    elif current == SearchWizard.kitchen.state:
        price_min = data.get("price_min", 0)
        price_max = data.get("price_max", 0)
        area_min = data.get("area_min", 0)
        area_text = f"от {area_min} м²" if area_min else "Не важно"
        await state.set_state(SearchWizard.area)
        await msg.edit_text(
            f"💰 Цена: <b>{_price_range_text(price_min, price_max)}</b>\n\n"
            f"📐 <b>Шаг 4/{TOTAL_STEPS}:</b> Минимальная общая площадь",
            reply_markup=area_keyboard(),
            parse_mode="HTML",
        )
    elif current == SearchWizard.renovation.state:
        area_min = data.get("area_min", 0)
        area_text = f"от {area_min} м²" if area_min else "Не важно"
        await state.set_state(SearchWizard.kitchen)
        await msg.edit_text(
            f"📐 Площадь: <b>{area_text}</b>\n\n"
            f"🍳 <b>Шаг 5/{TOTAL_STEPS}:</b> Минимальная площадь кухни",
            reply_markup=kitchen_keyboard(),
            parse_mode="HTML",
        )
    elif current == SearchWizard.pets.state:
        renovation_types = data.get("renovation_types", [])
        kitchen_min = data.get("kitchen_area_min", 0)
        kitchen_text = f"от {kitchen_min} м²" if kitchen_min else "Не важно"
        await state.set_state(SearchWizard.renovation)
        await msg.edit_text(
            f"🍳 Кухня: <b>{kitchen_text}</b>\n\n"
            f"🔧 <b>Шаг 6/{TOTAL_STEPS}:</b> Допустимый тип ремонта",
            reply_markup=renovation_keyboard(renovation_types),
            parse_mode="HTML",
        )
    elif current == SearchWizard.commission.state:
        await state.set_state(SearchWizard.pets)
        await msg.edit_text(
            f"🔧 Ремонт: <b>{', '.join(RenovationType.label(r) for r in data.get('renovation_types', [])) or 'Любой'}</b>\n\n"
            f"🐾 <b>Шаг 7/{TOTAL_STEPS}:</b> Фильтр по животным",
            reply_markup=pets_keyboard(),
            parse_mode="HTML",
        )
    elif current == SearchWizard.tolerance.state:
        await state.set_state(SearchWizard.commission)
        await msg.edit_text(
            f"🐾 Животные: <b>{'Скрывать с запретом' if data.get('pets_allowed') else 'Показывать все'}</b>\n\n"
            f"💼 <b>Шаг 8/{TOTAL_STEPS}:</b> Фильтр по комиссии",
            reply_markup=commission_keyboard(),
            parse_mode="HTML",
        )
    elif current == SearchWizard.initial_listings.state:
        await state.set_state(SearchWizard.tolerance)
        await msg.edit_text(
            f"💼 Комиссия: <b>{_commission_label(data.get('commission_max_percent', 100))}</b>\n\n"
            f"📊 <b>Шаг 9/{TOTAL_STEPS}:</b> Допуск для «почти подходящих» объявлений\n"
            "Если объявление чуть-чуть не попадает в критерии (цена, площадь), "
            "оно придёт с пометкой.",
            reply_markup=tolerance_keyboard(),
            parse_mode="HTML",
        )
    elif current == SearchWizard.confirm.state:
        await state.set_state(SearchWizard.initial_listings)
        await msg.edit_text(
            f"📋 <b>Шаг {TOTAL_STEPS}/{TOTAL_STEPS}:</b> Сколько объявлений показать сразу при запуске?",
            reply_markup=initial_listings_keyboard(),
            parse_mode="HTML",
        )

    await callback.answer()


# ── Подтверждение ──────────────────────────────────────────────────

@router.callback_query(SearchWizard.confirm, F.data.startswith("confirm:"))
async def on_confirm(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
    if await _is_rate_limited_callback(callback):
        return
    parts = _parse_callback_parts(callback.data, "confirm", expected_parts=2)
    if parts is None:
        await _reject_bad_callback(callback)
        return
    action = parts[1]
    if action not in {"start", "restart"}:
        await _reject_bad_callback(callback)
        return

    if action == "restart":
        await state.clear()
        await cmd_search(callback.message, state, skip_rate_limit=True)  # type: ignore[arg-type]
        await callback.answer()
        return

    data = await state.get_data()
    user_id = callback.from_user.id

    user_filter = UserFilter(
        user_id=user_id,
        cities=data.get("cities", [1]),
        rooms=data.get("rooms", []),
        price_min=data.get("price_min", 0),
        price_max=data.get("price_max", 0),
        area_min=data.get("area_min", 0),
        kitchen_area_min=data.get("kitchen_area_min", 0),
        renovation_types=data.get("renovation_types", []),
        pets_allowed=data.get("pets_allowed", True),
        commission_max_percent=data.get("commission_max_percent", 100),
        tolerance_percent=data.get("tolerance_percent", 0),
        initial_listings_count=data.get("initial_listings_count", 0),
        is_active=True,
    )

    await db.upsert_filter(user_filter)
    await state.clear()

    await callback.message.edit_text(  # type: ignore[union-attr]
        "✅ <b>Мониторинг запущен!</b>\n\n"
        "Я буду проверять ЦИАН, Авито и Яндекс Недвижимость "
        "каждые несколько минут и присылать новые объявления.\n\n"
        "/pause — приостановить\n"
        "/filters — посмотреть фильтры",
        parse_mode="HTML",
    )
    await callback.answer("Мониторинг запущен!")

    if user_filter.initial_listings_count > 0:
        asyncio.create_task(
            send_initial_listings(callback.bot, db, user_filter, config)
        )


# ── Редактирование фильтра ─────────────────────────────────────────

async def _save_edit_filter_and_show(
    callback_or_msg: CallbackQuery | Message,
    state: FSMContext,
    db: Database,
    user_id: int,
    edit_field: str,
) -> None:
    """Сохраняет изменённый фильтр и показывает сводку."""
    base = await db.get_filter(user_id)
    if base is None:
        return
    data = await state.get_data()
    updated = _fsm_data_to_user_filter(data, base, user_id, edit_field)
    await db.upsert_filter(updated)
    await state.clear()
    if isinstance(callback_or_msg, CallbackQuery):
        msg = callback_or_msg.message
        use_answer = False
    else:
        msg = callback_or_msg
        use_answer = True
    if msg is not None:
        await _show_filters_view(
            msg, db=db, user_id=user_id,
            edit_text="✅ Фильтр обновлён.", with_menu=True, use_answer=use_answer
        )


async def _show_filters_view(
    msg: Message,
    *,
    db: Database,
    user_id: int,
    edit_text: str | None = None,
    with_menu: bool = False,
    use_answer: bool = False,
) -> None:
    """Показывает сводку фильтров. use_answer=True — отправить новое сообщение (для message handler)."""
    user_filter = await db.get_filter(user_id)
    if user_filter is None:
        return
    summary = _build_summary_from_filter(user_filter)
    status = "🟢 Активен" if user_filter.is_active else "🔴 Приостановлен"
    text = f"<b>Ваши фильтры</b> ({status}):\n\n{summary}"
    if edit_text:
        text += f"\n\n{edit_text}"
    markup = edit_filter_menu_keyboard() if with_menu else edit_filter_single_button_keyboard()
    if use_answer:
        await msg.answer(text, reply_markup=markup, parse_mode="HTML")
    else:
        await msg.edit_text(text, reply_markup=markup, parse_mode="HTML")


@router.callback_query(F.data == "edit_filter:menu")
async def on_edit_filter_menu(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
    """Показывает меню выбора фильтра для изменения."""
    if await _is_rate_limited_callback(callback):
        return
    user_filter = await db.get_filter(callback.from_user.id)
    if user_filter is None:
        await callback.answer("Сначала настройте фильтры: /search", show_alert=True)
        return
    await callback.message.edit_text(  # type: ignore[union-attr]
        "<b>Какой фильтр изменить?</b>",
        reply_markup=edit_filter_menu_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "edit_filter:back")
async def on_edit_filter_back(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
    """Возврат к просмотру фильтров без сохранения."""
    if await _is_rate_limited_callback(callback):
        return
    await state.clear()
    msg = callback.message
    if msg is not None:
        await _show_filters_view(msg, db=db, user_id=callback.from_user.id)
    await callback.answer()


_EDIT_FILTER_FIELDS = frozenset(
    {"city", "rooms", "price", "area", "kitchen", "renovation", "pets", "commission", "tolerance", "initial_listings"}
)


@router.callback_query(F.data.startswith("edit_filter:"))
async def on_edit_filter_select(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
    """Вход в редактирование конкретного фильтра."""
    if await _is_rate_limited_callback(callback):
        return
    parts = (callback.data or "").split(":", 1)
    if len(parts) != 2 or parts[1] not in _EDIT_FILTER_FIELDS:
        await callback.answer()
        return
    edit_field = parts[1]
    user_filter = await db.get_filter(callback.from_user.id)
    if user_filter is None:
        await callback.answer("Сначала настройте фильтры: /search", show_alert=True)
        return

    fsm_data = _user_filter_to_fsm_data(user_filter)
    fsm_data["edit_filter"] = edit_field
    await state.update_data(**fsm_data)
    msg = callback.message
    if msg is None:
        await callback.answer()
        return

    if edit_field == "city":
        await state.set_state(SearchWizard.city)
        cities_text = get_cities_display(user_filter.cities)
        await msg.edit_text(
            f"✏️ <b>Изменить города</b>\n\nТекущие: {cities_text}\n\n"
            f"Выберите из списка или введите название:",
            reply_markup=city_millioners_keyboard(user_filter.cities),
            parse_mode="HTML",
        )
    elif edit_field == "rooms":
        await state.set_state(SearchWizard.rooms)
        rooms_text = ", ".join(f"{r}-комн." for r in sorted(user_filter.rooms)) if user_filter.rooms else "Любые"
        cities_text = get_cities_display(user_filter.cities)
        await msg.edit_text(
            f"✏️ <b>Изменить комнаты</b>\n\n"
            f"Города: {cities_text}\nТекущие комнаты: {rooms_text}\n\n"
            f"Выберите количество комнат:",
            reply_markup=rooms_keyboard(user_filter.rooms),
            parse_mode="HTML",
        )
    elif edit_field == "price":
        await state.set_state(SearchWizard.price)
        rooms = user_filter.rooms
        rooms_text = ", ".join(f"{r}-комн." for r in sorted(rooms)) if rooms else "Любые"
        await msg.edit_text(
            f"✏️ <b>Изменить цену</b>\n\nТекущий диапазон: {_price_range_text(user_filter.price_min, user_filter.price_max)}\n\n"
            f"Выберите ценовой диапазон:",
            reply_markup=price_keyboard(),
            parse_mode="HTML",
        )
    elif edit_field == "area":
        await state.set_state(SearchWizard.area)
        price_min, price_max = user_filter.price_min, user_filter.price_max
        await msg.edit_text(
            f"✏️ <b>Изменить площадь</b>\n\n"
            f"Текущая: от {user_filter.area_min} м²\n\n"
            f"Выберите минимальную площадь:",
            reply_markup=area_keyboard(),
            parse_mode="HTML",
        )
    elif edit_field == "kitchen":
        await state.set_state(SearchWizard.kitchen)
        area_text = f"от {user_filter.area_min} м²" if user_filter.area_min else "Не важно"
        await msg.edit_text(
            f"✏️ <b>Изменить площадь кухни</b>\n\n"
            f"Текущая: {area_text}\n\nВыберите минимальную площадь кухни:",
            reply_markup=kitchen_keyboard(),
            parse_mode="HTML",
        )
    elif edit_field == "renovation":
        await state.set_state(SearchWizard.renovation)
        names = ", ".join(RenovationType.label(r) for r in user_filter.renovation_types) if user_filter.renovation_types else "Любой"
        await msg.edit_text(
            f"✏️ <b>Изменить ремонт</b>\n\nТекущий: {names}\n\nВыберите тип ремонта:",
            reply_markup=renovation_keyboard(user_filter.renovation_types),
            parse_mode="HTML",
        )
    elif edit_field == "pets":
        await state.set_state(SearchWizard.pets)
        pets_text = "Скрывать с запретом" if user_filter.pets_allowed else "Показывать все"
        await msg.edit_text(
            f"✏️ <b>Изменить фильтр по животным</b>\n\nТекущий: {pets_text}\n\nВыберите:",
            reply_markup=pets_keyboard(),
            parse_mode="HTML",
        )
    elif edit_field == "commission":
        await state.set_state(SearchWizard.commission)
        comm_label = _commission_label(user_filter.commission_max_percent)
        await msg.edit_text(
            f"✏️ <b>Изменить фильтр по комиссии</b>\n\nТекущий: {comm_label}\n\nВыберите:",
            reply_markup=commission_keyboard(),
            parse_mode="HTML",
        )
    elif edit_field == "tolerance":
        await state.set_state(SearchWizard.tolerance)
        tol = user_filter.tolerance_percent
        tol_text = f"{tol}%" if tol else "Отключён"
        await msg.edit_text(
            f"✏️ <b>Изменить допуск</b>\n\nТекущий: {tol_text}\n\nВыберите допуск:",
            reply_markup=tolerance_keyboard(),
            parse_mode="HTML",
        )
    elif edit_field == "initial_listings":
        await state.set_state(SearchWizard.initial_listings)
        count = user_filter.initial_listings_count
        count_text = f"{count} объявлений" if count else "отключено"
        await msg.edit_text(
            f"✏️ <b>Изменить количество при запуске</b>\n\nТекущее: {count_text}\n\n"
            f"Сколько объявлений показать сразу при запуске?",
            reply_markup=initial_listings_keyboard(),
            parse_mode="HTML",
        )

    await callback.answer()


# ── nav: callback (inline-кнопки быстрых действий) ──────────────────

@router.callback_query(F.data.startswith("nav:"))
async def on_nav_callback(
    callback: CallbackQuery,
    state: FSMContext,
    db: Database,
) -> None:
    """Обработка inline-кнопок навигации (Поиск, Фильтры, Пауза, Возобновить)."""
    if await _is_rate_limited_callback(callback):
        return
    parts = _parse_callback_parts(callback.data, "nav", expected_parts=2)
    if parts is None or callback.message is None:
        await callback.answer()
        return

    action = parts[1]
    msg = callback.message

    if action == "search":
        await _start_search_wizard(msg, state)
    elif action == "filters":
        user_filter = await db.get_filter(callback.from_user.id)  # type: ignore[union-attr]
        if user_filter is None:
            await msg.answer("У вас пока нет фильтров. Используйте /search для настройки.")
        else:
            summary = _build_summary_from_filter(user_filter)
            status = "🟢 Активен" if user_filter.is_active else "🔴 Приостановлен"
            await msg.answer(
                f"<b>Ваши фильтры</b> ({status}):\n\n{summary}",
                reply_markup=edit_filter_single_button_keyboard(),
                parse_mode="HTML",
            )
    elif action == "pause":
        await db.set_active(callback.from_user.id, active=False)  # type: ignore[union-attr]
        await msg.answer("⏸ Мониторинг приостановлен. /resume — возобновить.")
    elif action == "resume":
        user_filter = await db.get_filter(callback.from_user.id)  # type: ignore[union-attr]
        if user_filter is None:
            await msg.answer("Сначала настройте фильтры: /search")
        else:
            await db.set_active(callback.from_user.id, active=True)  # type: ignore[union-attr]
            await msg.answer("▶️ Мониторинг возобновлён!")
    else:
        await callback.answer()
        return

    await callback.answer()


# ── /filters ───────────────────────────────────────────────────────

@router.message(Command("filters"))
async def cmd_filters(message: Message, db: Database) -> None:
    """Показ текущих фильтров пользователя."""
    if await _is_rate_limited_message(message):
        return
    user_filter = await db.get_filter(message.from_user.id)  # type: ignore[union-attr]

    if user_filter is None:
        await message.answer(
            "У вас пока нет фильтров. Используйте /search для настройки."
        )
        return

    summary = _build_summary_from_filter(user_filter)
    status = "🟢 Активен" if user_filter.is_active else "🔴 Приостановлен"

    await message.answer(
        f"<b>Ваши фильтры</b> ({status}):\n\n{summary}",
        reply_markup=edit_filter_single_button_keyboard(),
        parse_mode="HTML",
    )


# ── /pause, /resume ───────────────────────────────────────────────

@router.message(Command("pause"))
async def cmd_pause(message: Message, db: Database) -> None:
    """Приостановка мониторинга."""
    if await _is_rate_limited_message(message):
        return
    await db.set_active(message.from_user.id, active=False)  # type: ignore[union-attr]
    await message.answer("⏸ Мониторинг приостановлен. /resume — возобновить.")


@router.message(Command("resume"))
async def cmd_resume(message: Message, db: Database) -> None:
    """Возобновление мониторинга."""
    if await _is_rate_limited_message(message):
        return
    user_filter = await db.get_filter(message.from_user.id)  # type: ignore[union-attr]
    if user_filter is None:
        await message.answer("Сначала настройте фильтры: /search")
        return

    await db.set_active(message.from_user.id, active=True)  # type: ignore[union-attr]
    await message.answer("▶️ Мониторинг возобновлён!")


# ── /settopic ───────────────────────────────────────────────────────

@router.message(Command("settopic"))
async def cmd_settopic(message: Message, db: Database) -> None:
    """Настройка темы группы для отправки объявлений администратору."""
    if await _is_rate_limited_message(message):
        return
    if message.from_user is None or message.from_user.id != config.admin_user_id:
        return
    if message.chat is None or message.message_thread_id is None:
        await message.answer(
            "Отправьте команду /settopic <b>внутри нужной темы</b> группы с включёнными темами.",
            parse_mode="HTML",
        )
        return
    await db.set_group_topic_config(message.chat.id, message.message_thread_id)
    await message.answer("✅ Тема настроена. Объявления будут отправляться сюда.")


# ── Неизвестная команда ────────────────────────────────────────────

KNOWN_COMMANDS = ("start", "search", "filters", "pause", "resume", "help")


def _find_closest_command(typed: str) -> str | None:
    """Возвращает наиболее похожую команду или None, если нет близких совпадений."""
    typed_clean = typed.lstrip("/").split()[0] if typed else ""
    if not typed_clean:
        return None
    matches = difflib.get_close_matches(typed_clean, KNOWN_COMMANDS, n=1, cutoff=0.6)
    return matches[0] if matches else None


@router.message(F.text.startswith("/"))
async def cmd_unknown(message: Message) -> None:
    """Реакция на неизвестную команду с подсказкой похожей команды."""
    if await _is_rate_limited_message(message):
        return
    typed = (message.text or "").strip()
    closest = _find_closest_command(typed)
    if closest:
        text = (
            f"Неизвестная команда. Возможно, вы имели в виду /{closest}?\n\n"
            "Введите /help, чтобы увидеть список всех доступных функций."
        )
    else:
        text = "Неизвестная команда. Введите /help, чтобы увидеть список доступных функций."
    await message.answer(text)


# ── Утилиты ────────────────────────────────────────────────────────

def _commission_label(commission_max_percent: int) -> str:
    """Человекочитаемое название допустимой комиссии."""
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


def _build_summary(data: dict) -> str:
    """Строит текстовое описание фильтров из FSM-данных."""
    lines: list[str] = []

    cities = data.get("cities", [1])
    lines.append(f"🏙 Города: {get_cities_display(cities)}")

    rooms = data.get("rooms", [])
    if rooms:
        lines.append(f"🚪 Комнаты: {', '.join(str(r) for r in sorted(rooms))}")
    else:
        lines.append("🚪 Комнаты: Любые")

    lines.append(f"💰 Цена: {_price_range_text(data.get('price_min', 0), data.get('price_max', 0))}")

    area = data.get("area_min", 0)
    lines.append(f"📐 Площадь: {'от ' + str(area) + ' м²' if area else 'Не важно'}")

    kitchen = data.get("kitchen_area_min", 0)
    lines.append(f"🍳 Кухня: {'от ' + str(kitchen) + ' м²' if kitchen else 'Не важно'}")

    renovation = data.get("renovation_types", [])
    if renovation:
        names = ", ".join(RenovationType.label(r) for r in renovation)
        lines.append(f"🔧 Ремонт: {names}")
    else:
        lines.append("🔧 Ремонт: Любой")

    pets = data.get("pets_allowed", True)
    lines.append(f"🐾 Животные: {'Скрывать с запретом' if pets else 'Показывать все'}")

    comm = data.get("commission_max_percent", 100)
    lines.append(f"💼 Комиссия: {_commission_label(comm)}")

    tolerance = data.get("tolerance_percent", 0)
    if tolerance:
        lines.append(f"📊 Допуск: {tolerance}%")
    else:
        lines.append("📊 Допуск: Отключён")

    initial_count = data.get("initial_listings_count", 0)
    if initial_count:
        lines.append(f"📋 Показать сразу: {initial_count} объявлений")
    else:
        lines.append("📋 Показать сразу: отключено")

    return "\n".join(lines)


def _build_summary_from_filter(f: UserFilter) -> str:
    """Строит текстовое описание фильтров из UserFilter."""
    return _build_summary({
        "cities": f.cities,
        "rooms": f.rooms,
        "price_min": f.price_min,
        "price_max": f.price_max,
        "area_min": f.area_min,
        "kitchen_area_min": f.kitchen_area_min,
        "renovation_types": f.renovation_types,
        "pets_allowed": f.pets_allowed,
        "commission_max_percent": f.commission_max_percent,
        "tolerance_percent": f.tolerance_percent,
        "initial_listings_count": f.initial_listings_count,
    })


def _user_filter_to_fsm_data(f: UserFilter) -> dict:
    """Преобразует UserFilter в словарь для state.update_data."""
    return {
        "cities": f.cities,
        "rooms": f.rooms,
        "price_min": f.price_min,
        "price_max": f.price_max,
        "area_min": f.area_min,
        "kitchen_area_min": f.kitchen_area_min,
        "renovation_types": f.renovation_types,
        "pets_allowed": f.pets_allowed,
        "commission_max_percent": f.commission_max_percent,
        "tolerance_percent": f.tolerance_percent,
        "initial_listings_count": f.initial_listings_count,
    }


def _fsm_data_to_user_filter(
    data: dict, base: UserFilter, user_id: int, edit_field: str
) -> UserFilter:
    """Создаёт UserFilter из base с обновлённым полем из data."""
    def g(key: str, default: object = None) -> object:
        return data.get(key, getattr(base, key, default))

    return UserFilter(
        user_id=user_id,
        cities=g("cities", [1]) if edit_field == "city" else base.cities,
        rooms=g("rooms", []) if edit_field == "rooms" else base.rooms,
        price_min=g("price_min", 0) if edit_field in ("price", "price_custom") else base.price_min,
        price_max=g("price_max", 0) if edit_field in ("price", "price_custom") else base.price_max,
        area_min=g("area_min", 0) if edit_field == "area" else base.area_min,
        kitchen_area_min=g("kitchen_area_min", 0) if edit_field == "kitchen" else base.kitchen_area_min,
        renovation_types=g("renovation_types", []) if edit_field == "renovation" else base.renovation_types,
        pets_allowed=g("pets_allowed", True) if edit_field == "pets" else base.pets_allowed,
        commission_max_percent=g("commission_max_percent", 100) if edit_field == "commission" else base.commission_max_percent,
        tolerance_percent=g("tolerance_percent", 0) if edit_field == "tolerance" else base.tolerance_percent,
        initial_listings_count=g("initial_listings_count", 0) if edit_field == "initial_listings" else base.initial_listings_count,
        is_active=base.is_active,
    )


def _parse_callback_parts(
    callback_data: str | None,
    prefix: str,
    *,
    expected_parts: int | None = None,
    minimum_parts: int | None = None,
    maximum_parts: int | None = None,
) -> list[str] | None:
    """Безопасно разбирает callback payload и проверяет его формат."""
    if not callback_data:
        return None
    if not callback_data.startswith(f"{prefix}:"):
        return None
    parts = callback_data.split(":")
    if expected_parts is not None and len(parts) != expected_parts:
        return None
    if minimum_parts is not None and len(parts) < minimum_parts:
        return None
    if maximum_parts is not None and len(parts) > maximum_parts:
        return None
    return parts


def _parse_int_in_range(
    value: str,
    *,
    minimum: int,
    maximum: int,
) -> int | None:
    """Проверяет, что значение целое и входит в заданный диапазон."""
    try:
        parsed = int(value)
    except ValueError:
        return None
    if parsed < minimum or parsed > maximum:
        return None
    return parsed


def _parse_price_input(raw: str | None) -> int | None:
    """Проверяет ввод цены пользователя и нормализует пробелы."""
    if raw is None:
        return None
    cleaned = raw.strip().replace(" ", "")
    if not cleaned.isdigit():
        return None
    return _parse_int_in_range(cleaned, minimum=0, maximum=MAX_PRICE_RUB)


def _is_rate_limited(user_id: int, *, now: float | None = None) -> bool:
    """Возвращает True, если пользователь превысил частоту запросов."""
    current = now if now is not None else time.monotonic()
    last_ts = _LAST_REQUEST_TS_BY_USER.get(user_id)
    if last_ts is not None and current - last_ts < RATE_LIMIT_SECONDS:
        return True
    _LAST_REQUEST_TS_BY_USER[user_id] = current
    return False


async def _is_rate_limited_message(message: Message) -> bool:
    """Проверяет лимит частоты для message-события."""
    if message.from_user is None:
        return False
    if _is_rate_limited(message.from_user.id):
        await message.answer("Слишком частые запросы. Попробуйте через секунду.")
        return True
    return False


async def _is_rate_limited_callback(callback: CallbackQuery) -> bool:
    """Проверяет лимит частоты для callback-события."""
    if _is_rate_limited(callback.from_user.id):
        await callback.answer("Слишком частые нажатия. Попробуйте через секунду.")
        return True
    return False


async def _reject_bad_callback(callback: CallbackQuery, *, text: str = "Некорректные данные запроса.") -> None:
    """Единая реакция на невалидный callback payload."""
    await callback.answer(text, show_alert=True)
