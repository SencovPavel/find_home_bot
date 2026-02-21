"""Тесты генерации inline-клавиатур."""

from __future__ import annotations

from src.bot.keyboards import (
    area_keyboard,
    city_keyboard,
    commission_keyboard,
    confirm_keyboard,
    kitchen_keyboard,
    pets_keyboard,
    price_keyboard,
    renovation_keyboard,
    rooms_keyboard,
    tolerance_keyboard,
)


def test_city_keyboard_has_two_cities() -> None:
    """Клавиатура городов содержит Москву и СПб."""
    kb = city_keyboard()
    texts = [btn.text for row in kb.inline_keyboard for btn in row]

    assert "Москва" in texts
    assert "Санкт-Петербург" in texts


def test_rooms_keyboard_marks_selected() -> None:
    """Выбранные комнаты помечаются галочкой."""
    kb = rooms_keyboard(selected=[2])
    texts = [btn.text for row in kb.inline_keyboard for btn in row]

    assert any("✓" in t and "2-комн." in t for t in texts)
    assert not any("✓" in t and "1-комн." in t for t in texts)


def test_rooms_keyboard_has_done_button() -> None:
    """Клавиатура содержит кнопку завершения."""
    kb = rooms_keyboard()
    texts = [btn.text for row in kb.inline_keyboard for btn in row]

    assert "Готово →" in texts


def test_price_keyboard_has_custom_option() -> None:
    """Клавиатура цен содержит опцию ручного ввода."""
    kb = price_keyboard()
    texts = [btn.text for row in kb.inline_keyboard for btn in row]

    assert "Ввести вручную" in texts


def test_area_keyboard_has_skip_option() -> None:
    """Клавиатура площади содержит опцию «Не важно»."""
    kb = area_keyboard()
    texts = [btn.text for row in kb.inline_keyboard for btn in row]

    assert "Не важно" in texts
    assert any("от 30 м²" in t for t in texts)


def test_kitchen_keyboard_has_options() -> None:
    """Клавиатура кухни содержит варианты и «Не важно»."""
    kb = kitchen_keyboard()
    texts = [btn.text for row in kb.inline_keyboard for btn in row]

    assert "Не важно" in texts
    assert any("от 6 м²" in t for t in texts)


def test_renovation_keyboard_marks_selected() -> None:
    """Выбранные типы ремонта помечаются галочкой."""
    kb = renovation_keyboard(selected=["euro"])
    texts = [btn.text for row in kb.inline_keyboard for btn in row]

    assert any("✓" in t and "Евроремонт" in t for t in texts)
    assert not any("✓" in t and "Косметический" in t for t in texts)


def test_renovation_keyboard_has_any_and_done() -> None:
    """Клавиатура ремонта содержит «Любой» и «Готово»."""
    kb = renovation_keyboard()
    texts = [btn.text for row in kb.inline_keyboard for btn in row]

    assert "Любой ремонт" in texts
    assert "Готово →" in texts


def test_pets_keyboard_has_two_options() -> None:
    """Клавиатура животных содержит две опции."""
    kb = pets_keyboard()
    texts = [btn.text for row in kb.inline_keyboard for btn in row]

    assert len(texts) == 2


def test_commission_keyboard_has_two_options() -> None:
    """Клавиатура комиссии содержит две опции."""
    kb = commission_keyboard()
    texts = [btn.text for row in kb.inline_keyboard for btn in row]

    assert "Только без комиссии" in texts
    assert "Не важно" in texts


def test_tolerance_keyboard_has_custom_option() -> None:
    """Клавиатура допуска содержит опцию ручного ввода."""
    kb = tolerance_keyboard()
    texts = [btn.text for row in kb.inline_keyboard for btn in row]

    assert "Ввести свой %" in texts
    assert "Отключить" in texts


def test_confirm_keyboard_has_start_and_restart() -> None:
    """Клавиатура подтверждения содержит запуск и перезапуск."""
    kb = confirm_keyboard()
    texts = [btn.text for row in kb.inline_keyboard for btn in row]

    assert "Запустить мониторинг" in texts
    assert "Настроить заново" in texts
