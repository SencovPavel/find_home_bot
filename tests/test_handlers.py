"""Тесты валидации и защит в handlers."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

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


@pytest.fixture
def mock_db() -> MagicMock:
    """Мок БД для тестов handlers с db."""
    return MagicMock()


@pytest.mark.asyncio
async def test_on_price_custom_max_rejects_when_max_less_than_min(mock_db: MagicMock) -> None:
    """Не принимает диапазон, где максимум меньше минимума."""
    state = DummyState(data={"price_min": 100_000})
    message = DummyMessage(user_id=9001, text="50 000")

    await handlers.on_price_custom_max(message, state, mock_db)  # type: ignore[arg-type]

    assert "Максимальная цена должна быть больше или равна минимальной." in message.answers
    assert "price_max" not in state.data


@pytest.mark.asyncio
async def test_on_price_custom_max_happy_path_updates_state(mock_db: MagicMock) -> None:
    """На валидном вводе сохраняет значение и переводит на следующий шаг."""
    state = DummyState(data={"price_min": 50_000})
    message = DummyMessage(user_id=9002, text="120000")

    await handlers.on_price_custom_max(message, state, mock_db)  # type: ignore[arg-type]

    assert state.data["price_max"] == 120000
    assert state.current_state == handlers.SearchWizard.area
    assert any("Шаг 4/" in text for text in message.answers)


def test_user_filter_to_fsm_data_roundtrip() -> None:
    """_user_filter_to_fsm_data и _fsm_data_to_user_filter работают корректно."""
    from src.parser.models import UserFilter

    f = UserFilter(
        user_id=1,
        city=2,
        rooms=[2, 3],
        price_min=50_000,
        price_max=150_000,
        area_min=40.0,
        kitchen_area_min=8.0,
        renovation_types=["euro"],
        pets_allowed=True,
        no_commission=True,
        tolerance_percent=10,
        initial_listings_count=5,
    )
    data = handlers._user_filter_to_fsm_data(f)
    assert data["city"] == 2
    assert data["rooms"] == [2, 3]
    assert data["price_min"] == 50_000
    assert data["no_commission"] is True

    updated = handlers._fsm_data_to_user_filter(
        {**data, "rooms": [1, 2]}, f, user_id=1, edit_field="rooms"
    )
    assert updated.rooms == [1, 2]
    assert updated.city == 2
    assert updated.price_min == 50_000


@pytest.mark.asyncio
async def test_cmd_filters_returns_message_with_keyboard(mock_db: MagicMock) -> None:
    """cmd_filters возвращает сообщение с inline-клавиатурой."""
    from src.parser.models import UserFilter

    mock_db.get_filter = AsyncMock(
        return_value=UserFilter(
            user_id=100,
            city=1,
            rooms=[2],
            price_min=0,
            price_max=100_000,
            is_active=True,
        ),
    )
    message = DummyMessage(user_id=100, text="/filters")

    await handlers.cmd_filters(message, mock_db)  # type: ignore[arg-type]

    assert len(message.answers) == 1
    assert "фильтры" in message.answers[0].lower() or "активен" in message.answers[0].lower()


@pytest.mark.asyncio
async def test_cmd_search_can_skip_rate_limit_for_internal_restart() -> None:
    """Внутренний перезапуск мастера не должен блокироваться throttling."""
    state = DummyState()
    message = DummyMessage(user_id=7001, text="/search")

    await handlers.cmd_search(message, state, skip_rate_limit=True)  # type: ignore[arg-type]

    assert state.current_state == handlers.SearchWizard.city
    assert any("Шаг 1/" in text for text in message.answers)
