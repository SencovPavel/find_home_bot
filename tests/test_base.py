"""Тесты утилит и защит парсера."""

from __future__ import annotations

from src.parser.base import MAX_HTML_SIZE_BYTES, is_captcha_page, parse_float


def test_parse_float_from_int() -> None:
    """Парсит целое число."""
    assert parse_float(42) == 42.0


def test_parse_float_from_string() -> None:
    """Парсит строковое представление числа."""
    assert parse_float("35.5") == 35.5


def test_parse_float_from_comma_string() -> None:
    """Парсит число с запятой-разделителем."""
    assert parse_float("35,5") == 35.5


def test_parse_float_from_none() -> None:
    """None возвращает 0.0."""
    assert parse_float(None) == 0.0


def test_parse_float_from_invalid_string() -> None:
    """Невалидная строка возвращает 0.0."""
    assert parse_float("abc") == 0.0


def test_parse_float_from_empty_string() -> None:
    """Пустая строка возвращает 0.0."""
    assert parse_float("") == 0.0


def test_is_captcha_page_detects_captcha() -> None:
    """Обнаруживает captcha по маркерам в начале страницы."""
    html_captcha = "<html><body>showcaptcha required</body></html>"
    assert is_captcha_page(html_captcha) is True


def test_is_captcha_page_detects_cf_challenge() -> None:
    """Обнаруживает CloudFlare challenge."""
    html = "<html><body><div class='cf-challenge'>Please wait</div></body></html>"
    assert is_captcha_page(html) is True


def test_is_captcha_page_detects_russian_marker() -> None:
    """Обнаруживает кириллический маркер 'проверка'."""
    html = "<html><body>Пройдите проверка безопасности</body></html>"
    assert is_captcha_page(html) is True


def test_is_captcha_page_passes_normal_html() -> None:
    """Обычная страница не распознаётся как captcha."""
    html = "<html><body><h1>Аренда квартир</h1></body></html>"
    assert is_captcha_page(html) is False


def test_is_captcha_page_checks_only_first_5000_chars() -> None:
    """Маркер captcha за пределами первых 5000 символов не обнаруживается."""
    padding = "x" * 5000
    html = f"<html><body>{padding}showcaptcha</body></html>"
    assert is_captcha_page(html) is False


def test_max_html_size_is_10mb() -> None:
    """Лимит HTML установлен в 10 МБ."""
    assert MAX_HTML_SIZE_BYTES == 10_000_000
