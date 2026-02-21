"""Inline-клавиатуры для пошаговой настройки фильтров поиска."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# ── Города ─────────────────────────────────────────────────────────

CITIES = {
    1: "Москва",
    2: "Санкт-Петербург",
}


def city_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора города."""
    buttons = [
        [InlineKeyboardButton(text=name, callback_data=f"city:{cid}")]
        for cid, name in CITIES.items()
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
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ── Животные ───────────────────────────────────────────────────────

def pets_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура: фильтровать объявления с запретом на животных."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Скрывать с запретом на животных", callback_data="pets:1")],
        [InlineKeyboardButton(text="Показывать все", callback_data="pets:0")],
    ])


# ── Комиссия ───────────────────────────────────────────────────────

def commission_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура: фильтровать объявления по комиссии."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Только без комиссии", callback_data="commission:1")],
        [InlineKeyboardButton(text="Не важно", callback_data="commission:0")],
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
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ── Подтверждение ──────────────────────────────────────────────────

def confirm_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура подтверждения настроек и запуска мониторинга."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Запустить мониторинг", callback_data="confirm:start")],
        [InlineKeyboardButton(text="Настроить заново", callback_data="confirm:restart")],
    ])
