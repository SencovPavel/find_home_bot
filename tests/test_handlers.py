"""Тесты валидации и защит в handlers."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace

import pytest

from src.bot import handlers


@pytest.fixture(autouse=True)
def clear_rate_limit_cache() -> None:
    """Изолирует тесты throttle от состояния других тестов."""
    handlers._LAST_REQUEST_TS_BY_USER.clear()


def test_parse_callback_parts_valid_and_invalid() -> None:
    """Проверяет безопасный разбор callback payload."""
    assert handlers._parse_callback_parts("price:10:20", "price", expected_parts=3) == [
        "price",
        "10",
        "20",
    ]
    assert handlers._parse_callback_parts("price:10", "price", expected_parts=3) is None
    assert handlers._parse_callback_parts("other:10:20", "price", expected_parts=3) is None
    assert handlers._parse_callback_parts(None, "price", expected_parts=3) is None


def test_parse_price_input_range_and_format() -> None:
    """Отклоняет нечисловой ввод и значения вне диапазона."""
    assert handlers._parse_price_input("100 000") == 100000
    assert handlers._parse_price_input("-10") is None
    assert handlers._parse_price_input("abc") is None
    assert handlers._parse_price_input(str(handlers.MAX_PRICE_RUB + 1)) is None


def test_rate_limit_blocks_too_frequent_calls() -> None:
    """Повторный запрос раньше лимита блокируется."""
    assert handlers._is_rate_limited(1, now=10.0) is False
    assert handlers._is_rate_limited(1, now=10.2) is True
    assert handlers._is_rate_limited(1, now=11.0) is False


@dataclass
class DummyState:
    """Минимальная реализация FSM-состояния для теста."""

    data: dict[str, object] = field(default_factory=dict)
    is_cleared: bool = False
    current_state: object | None = None

    async def get_data(self) -> dict[str, object]:
        return self.data

    async def update_data(self, **kwargs: object) -> None:
        self.data.update(kwargs)

    async def clear(self) -> None:
        self.is_cleared = True
        self.data.clear()

    async def set_state(self, state: object) -> None:
        self.current_state = state


@dataclass
class DummyMessage:
    """Минимальная реализация Message с накоплением ответов."""

    user_id: int
    text: str | None
    answers: list[str] = field(default_factory=list)

    @property
    def from_user(self) -> SimpleNamespace:
        return SimpleNamespace(id=self.user_id)

    async def answer(self, text: str, **_: object) -> None:
        self.answers.append(text)


@pytest.mark.asyncio
async def test_on_price_custom_max_rejects_when_max_less_than_min() -> None:
    """Не принимает диапазон, где максимум меньше минимума."""
    state = DummyState(data={"price_min": 100_000})
    message = DummyMessage(user_id=9001, text="50 000")

    await handlers.on_price_custom_max(message, state)  # type: ignore[arg-type]

    assert "Максимальная цена должна быть больше или равна минимальной." in message.answers
    assert "price_max" not in state.data


@pytest.mark.asyncio
async def test_on_price_custom_max_happy_path_updates_state() -> None:
    """На валидном вводе сохраняет значение и переводит на следующий шаг."""
    state = DummyState(data={"price_min": 50_000})
    message = DummyMessage(user_id=9002, text="120000")

    await handlers.on_price_custom_max(message, state)  # type: ignore[arg-type]

    assert state.data["price_max"] == 120000
    assert state.current_state == handlers.SearchWizard.area
    assert any("Шаг 4/9" in text for text in message.answers)


@pytest.mark.asyncio
async def test_cmd_search_can_skip_rate_limit_for_internal_restart() -> None:
    """Внутренний перезапуск мастера не должен блокироваться throttling."""
    state = DummyState()
    message = DummyMessage(user_id=7001, text="/search")

    await handlers.cmd_search(message, state, skip_rate_limit=True)  # type: ignore[arg-type]

    assert state.current_state == handlers.SearchWizard.city
    assert any("Шаг 1/9" in text for text in message.answers)
