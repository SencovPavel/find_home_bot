"""Тесты утилит парсера."""

from __future__ import annotations

from src.parser.base import parse_float


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
