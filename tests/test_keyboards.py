"""Тесты генерации inline-клавиатур."""

from __future__ import annotations

from src.bot.keyboards import (
    area_keyboard,
    city_millioners_keyboard,
    city_search_results_keyboard,
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
from src.data.cities import City


def test_city_search_results_keyboard_shows_found_cities() -> None:
    """Клавиатура результатов поиска отображает переданные города."""
    cities = [
        City(1, "Москва", 1, "moskva"),
        City(2, "Санкт-Петербург", 2, "sankt-peterburg"),
    ]
    kb = city_search_results_keyboard(cities)
    texts = [btn.text for row in kb.inline_keyboard for btn in row]

    assert texts == ["Москва", "Санкт-Петербург"]


def test_city_search_results_keyboard_callback_data() -> None:
    """Callback data содержит ID города."""
    cities = [City(42, "Тестград", 100, "testgrad")]
    kb = city_search_results_keyboard(cities)
    data = [btn.callback_data for row in kb.inline_keyboard for btn in row]

    assert data == ["city:42"]


def test_city_search_results_keyboard_empty_list() -> None:
    """Пустой список городов — пустая клавиатура."""
    kb = city_search_results_keyboard([])
    assert kb.inline_keyboard == []


def test_city_millioners_keyboard_has_top_cities() -> None:
    """Клавиатура городов-миллионников содержит Москву, СПб, Новосибирск."""
    kb = city_millioners_keyboard()
    texts = [btn.text for row in kb.inline_keyboard for btn in row]

    assert "Москва" in texts
    assert "Санкт-Петербург" in texts
    assert "Новосибирск" in texts
    assert "Екатеринбург" in texts


def test_city_millioners_keyboard_two_per_row() -> None:
    """Города-миллионники расположены по 2 кнопки в ряд."""
    kb = city_millioners_keyboard()
    for row in kb.inline_keyboard:
        assert len(row) <= 2


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


def test_pets_keyboard_has_two_options_and_back() -> None:
    """Клавиатура животных содержит две опции и кнопку «Назад»."""
    kb = pets_keyboard()
    texts = [btn.text for row in kb.inline_keyboard for btn in row]

    assert "Скрывать с запретом на животных" in texts
    assert "Показывать все" in texts
    assert "← Назад" in texts


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


def test_initial_listings_keyboard_has_options() -> None:
    """Клавиатура «показать сразу» содержит Отключить, 5, 10 и Ввести число."""
    kb = initial_listings_keyboard()
    texts = [btn.text for row in kb.inline_keyboard for btn in row]
    assert "Отключить" in texts
    assert "5" in texts
    assert "10" in texts
    assert "Ввести число" in texts


def test_edit_filter_menu_keyboard_has_filter_options() -> None:
    """Меню редактирования фильтра содержит кнопки Город, Комнаты, Цена и т.д."""
    kb = edit_filter_menu_keyboard()
    texts = [btn.text for row in kb.inline_keyboard for btn in row]

    assert "Город" in texts
    assert "Комнаты" in texts
    assert "Цена" in texts
    assert "← К фильтрам" in texts


def test_edit_filter_single_button_keyboard_has_edit_button() -> None:
    """Кнопка «Изменить фильтр» для cmd_filters."""
    kb = edit_filter_single_button_keyboard()
    texts = [btn.text for row in kb.inline_keyboard for btn in row]
    callback_datas = [btn.callback_data for row in kb.inline_keyboard for btn in row]

    assert any("Изменить фильтр" in t for t in texts)
    assert "edit_filter:menu" in callback_datas


def test_confirm_keyboard_has_start_and_restart() -> None:
    """Клавиатура подтверждения содержит запуск и перезапуск."""
    kb = confirm_keyboard()
    texts = [btn.text for row in kb.inline_keyboard for btn in row]

    assert "Запустить мониторинг" in texts
    assert "Настроить заново" in texts
