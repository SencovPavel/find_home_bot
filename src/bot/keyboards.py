"""Inline-клавиатуры для пошаговой настройки фильтров поиска."""

from __future__ import annotations

from typing import List

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from src.data.cities import City, get_millioner_cities

BACK_BUTTON = InlineKeyboardButton(text="← Назад", callback_data="back")

# ── Города ─────────────────────────────────────────────────────────


def city_millioners_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура быстрого выбора городов-миллионников (2 кнопки в ряд)."""
    cities = get_millioner_cities()
    buttons: List[List[InlineKeyboardButton]] = []
    row: List[InlineKeyboardButton] = []
    for c in cities:
        row.append(InlineKeyboardButton(text=c.name, callback_data=f"city:{c.id}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def city_search_results_keyboard(cities: List[City]) -> InlineKeyboardMarkup:
    """Динамическая клавиатура из результатов поиска городов."""
    buttons = [
        [InlineKeyboardButton(text=c.name, callback_data=f"city:{c.id}")]
        for c in cities
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ── Количество комнат ──────────────────────────────────────────────

def rooms_keyboard(selected: list[int] | None = None) -> InlineKeyboardMarkup:
    """Клавиатура выбора количества комнат (мульти-выбор)."""
    selected = selected or []
    options = [1, 2, 3, 4]
    buttons: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []

    for n in options:
        mark = "✓ " if n in selected else ""
        row.append(InlineKeyboardButton(
            text=f"{mark}{n}-комн.",
            callback_data=f"rooms:{n}",
        ))

    buttons.append(row)
    buttons.append([
        InlineKeyboardButton(text="Студия", callback_data="rooms:0"),
    ])
    buttons.append([
        InlineKeyboardButton(text="Готово →", callback_data="rooms:done"),
    ])
    buttons.append([BACK_BUTTON])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ── Цена ───────────────────────────────────────────────────────────

PRICE_RANGES = [
    (0, 30_000, "до 30 000 ₽"),
    (0, 50_000, "до 50 000 ₽"),
    (0, 80_000, "до 80 000 ₽"),
    (0, 100_000, "до 100 000 ₽"),
    (50_000, 100_000, "50 000 – 100 000 ₽"),
    (100_000, 150_000, "100 000 – 150 000 ₽"),
    (100_000, 200_000, "100 000 – 200 000 ₽"),
]


def price_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура быстрого выбора ценового диапазона."""
    buttons = [
        [InlineKeyboardButton(
            text=label,
            callback_data=f"price:{pmin}:{pmax}",
        )]
        for pmin, pmax, label in PRICE_RANGES
    ]
    buttons.append([
        InlineKeyboardButton(text="Ввести вручную", callback_data="price:custom"),
    ])
    buttons.append([BACK_BUTTON])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ── Площадь ────────────────────────────────────────────────────────

AREA_OPTIONS = [30, 40, 50, 60, 70]


def area_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура минимальной площади."""
    buttons = [
        [InlineKeyboardButton(
            text=f"от {a} м²",
            callback_data=f"area:{a}",
        )]
        for a in AREA_OPTIONS
    ]
    buttons.append([
        InlineKeyboardButton(text="Не важно", callback_data="area:0"),
    ])
    buttons.append([BACK_BUTTON])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ── Площадь кухни ──────────────────────────────────────────────────

KITCHEN_OPTIONS = [6, 8, 10, 12, 15]


def kitchen_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура минимальной площади кухни."""
    buttons = [
        [InlineKeyboardButton(
            text=f"от {k} м²",
            callback_data=f"kitchen:{k}",
        )]
        for k in KITCHEN_OPTIONS
    ]
    buttons.append([
        InlineKeyboardButton(text="Не важно", callback_data="kitchen:0"),
    ])
    buttons.append([BACK_BUTTON])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ── Тип ремонта ────────────────────────────────────────────────────

RENOVATION_OPTIONS = {
    "cosmetic": "Косметический",
    "euro": "Евроремонт",
    "designer": "Дизайнерский",
}


def renovation_keyboard(selected: list[str] | None = None) -> InlineKeyboardMarkup:
    """Клавиатура выбора типов ремонта (мульти-выбор)."""
    selected = selected or []
    buttons: list[list[InlineKeyboardButton]] = []

    for key, label in RENOVATION_OPTIONS.items():
        mark = "✓ " if key in selected else ""
        buttons.append([InlineKeyboardButton(
            text=f"{mark}{label}",
            callback_data=f"renovation:{key}",
        )])

    buttons.append([
        InlineKeyboardButton(text="Любой ремонт", callback_data="renovation:any"),
    ])
    buttons.append([
        InlineKeyboardButton(text="Готово →", callback_data="renovation:done"),
    ])
    buttons.append([BACK_BUTTON])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ── Животные ───────────────────────────────────────────────────────

def pets_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура: фильтровать объявления с запретом на животных."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Скрывать с запретом на животных", callback_data="pets:1")],
        [InlineKeyboardButton(text="Показывать все", callback_data="pets:0")],
        [BACK_BUTTON],
    ])


# ── Комиссия ───────────────────────────────────────────────────────

def commission_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура: фильтровать объявления по комиссии."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Только без комиссии", callback_data="commission:1")],
        [InlineKeyboardButton(text="Не важно", callback_data="commission:0")],
        [BACK_BUTTON],
    ])


# ── Допуск (tolerance) ─────────────────────────────────────────────

TOLERANCE_OPTIONS = [
    (0, "Отключить"),
    (10, "10%"),
    (15, "15%"),
    (20, "20%"),
]


def tolerance_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора допуска для «почти подходящих» объявлений."""
    buttons = [
        [InlineKeyboardButton(
            text=label,
            callback_data=f"tolerance:{value}",
        )]
        for value, label in TOLERANCE_OPTIONS
    ]
    buttons.append([
        InlineKeyboardButton(text="Ввести свой %", callback_data="tolerance:custom"),
    ])
    buttons.append([BACK_BUTTON])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ── Показать сразу при старте ──────────────────────────────────────

INITIAL_LISTINGS_OPTIONS = [
    (0, "Отключить"),
    (5, "5"),
    (10, "10"),
    (15, "15"),
    (20, "20"),
]


def initial_listings_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура: сколько объявлений показать сразу при запуске мониторинга."""
    buttons = [
        [InlineKeyboardButton(
            text=label,
            callback_data=f"initial_listings:{value}",
        )]
        for value, label in INITIAL_LISTINGS_OPTIONS
    ]
    buttons.append([
        InlineKeyboardButton(text="Ввести число", callback_data="initial_listings:custom"),
    ])
    buttons.append([BACK_BUTTON])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ── Редактирование фильтра ─────────────────────────────────────────

EDIT_FILTER_OPTIONS = [
    ("city", "Город"),
    ("rooms", "Комнаты"),
    ("price", "Цена"),
    ("area", "Площадь"),
    ("kitchen", "Кухня"),
    ("renovation", "Ремонт"),
    ("pets", "Животные"),
    ("commission", "Комиссия"),
    ("tolerance", "Допуск"),
    ("initial_listings", "Показать сразу"),
]


def edit_filter_menu_keyboard() -> InlineKeyboardMarkup:
    """Меню выбора фильтра для изменения."""
    buttons: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for key, label in EDIT_FILTER_OPTIONS:
        row.append(InlineKeyboardButton(text=label, callback_data=f"edit_filter:{key}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton(text="← К фильтрам", callback_data="edit_filter:back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def edit_filter_single_button_keyboard() -> InlineKeyboardMarkup:
    """Одна кнопка «Изменить фильтр» для cmd_filters."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Изменить фильтр", callback_data="edit_filter:menu")],
    ])


# ── Подтверждение ──────────────────────────────────────────────────

def confirm_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура подтверждения настроек и запуска мониторинга."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Запустить мониторинг", callback_data="confirm:start")],
        [InlineKeyboardButton(text="Настроить заново", callback_data="confirm:restart")],
        [BACK_BUTTON],
    ])
