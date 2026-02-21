"""Тесты валидации initData Telegram Web App."""

from __future__ import annotations

import pytest

from src.webapp.validation import validate_init_data


def test_validate_init_data_empty_returns_none() -> None:
    """Пустая initData возвращает None."""
    assert validate_init_data("", "token") is None
    assert validate_init_data(" ", "token") is None


def test_validate_init_data_invalid_hash_returns_none() -> None:
    """Неверная подпись возвращает None."""
    init = "query_id=AAHdF6IQAAAAAN0XohAOEd&user=%7B%22id%22%3A123%7D&auth_date=1234567890&hash=wrong"
    assert validate_init_data(init, "bot_token") is None


def test_validate_init_data_no_hash_returns_none() -> None:
    """Отсутствие hash возвращает None."""
    init = "user=%7B%22id%22%3A123%7D&auth_date=1234567890"
    assert validate_init_data(init, "token") is None
