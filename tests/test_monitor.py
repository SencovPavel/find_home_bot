"""Тесты логики мониторинга: уведомление об отсутствии объявлений."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from src.parser.models import Listing, MetroTransport, Source, UserFilter
from src.scheduler.monitor import _process_user, send_initial_listings


def _make_listing(listing_id: int, price: int = 100_000) -> Listing:
    """Создаёт тестовое объявление."""
    return Listing(
        listing_id=listing_id,
        source=Source.CIAN,
        url="https://www.cian.ru/rent/flat/123/",
        title="2-комн. квартира",
        price=price,
        address="Москва",
        metro_station="Тверская",
        metro_distance_min=7,
        metro_transport=MetroTransport.WALK,
        total_area=55.0,
        kitchen_area=12.0,
        rooms=2,
        floor=3,
        total_floors=12,
        renovation="euro",
        description="Уютная квартира в центре",
        photos=[],
    )


@pytest.mark.asyncio
@patch("src.scheduler.monitor._aggregate_listings")
async def test_send_initial_listings_zero_from_parsers_sends_notification(
    mock_aggregate: AsyncMock,
) -> None:
    """send_initial_listings: 0 объявлений от парсеров → отправляется уведомление."""
    mock_aggregate.return_value = []
    bot = AsyncMock()
    db = AsyncMock()
    db.is_seen = AsyncMock(return_value=False)

    user_filter = UserFilter(
        user_id=42,
        cities=[1],
        initial_listings_count=5,
        is_active=True,
    )

    result = await send_initial_listings(bot, db, user_filter)

    assert result == 0
    bot.send_message.assert_called_once()
    call_kwargs = bot.send_message.call_args[1]
    assert "нет объявлений" in call_kwargs["text"]
    db.mark_empty_notified.assert_called_once_with(42)


@pytest.mark.asyncio
@patch("src.scheduler.monitor._aggregate_listings")
async def test_send_initial_listings_all_matching_seen_no_notification(
    mock_aggregate: AsyncMock,
) -> None:
    """send_initial_listings: есть объявления, все подходящие уже seen → уведомление не отправляется."""
    listing = _make_listing(1)
    mock_aggregate.return_value = [listing]
    bot = AsyncMock()
    db = AsyncMock()
    db.is_seen = AsyncMock(return_value=True)

    user_filter = UserFilter(
        user_id=42,
        cities=[1],
        price_min=50_000,
        price_max=150_000,
        area_min=40.0,
        kitchen_area_min=8.0,
        rooms=[2],
        renovation_types=["euro"],
        initial_listings_count=5,
        is_active=True,
    )

    result = await send_initial_listings(bot, db, user_filter)

    assert result == 0
    bot.send_message.assert_not_called()
    db.mark_empty_notified.assert_not_called()


@pytest.mark.asyncio
@patch("src.scheduler.monitor._aggregate_listings")
async def test_send_initial_listings_has_unseen_matching_no_notification(
    mock_aggregate: AsyncMock,
) -> None:
    """send_initial_listings: есть непросмотренные подходящие → уведомление не отправляется."""
    listing = _make_listing(1)
    mock_aggregate.return_value = [listing]
    bot = AsyncMock()
    db = AsyncMock()
    db.is_seen = AsyncMock(return_value=False)

    user_filter = UserFilter(
        user_id=42,
        cities=[1],
        price_min=50_000,
        price_max=150_000,
        area_min=40.0,
        kitchen_area_min=8.0,
        rooms=[2],
        renovation_types=["euro"],
        initial_listings_count=5,
        is_active=True,
    )

    result = await send_initial_listings(bot, db, user_filter)

    assert result == 1
    # Empty notification не отправляется (mark_empty_notified не вызывается)
    db.mark_empty_notified.assert_not_called()


@pytest.mark.asyncio
@patch("src.scheduler.monitor._aggregate_listings")
async def test_process_user_zero_matching_sends_notification_and_marks(
    mock_aggregate: AsyncMock,
) -> None:
    """_process_user: 0 matching, empty_notified_at is None → отправляется уведомление и mark_empty_notified."""
    mock_aggregate.return_value = []
    bot = AsyncMock()
    db = AsyncMock()

    user_filter = UserFilter(
        user_id=42,
        cities=[1],
        initial_listings_count=5,
        is_active=True,
        empty_notified_at=None,
    )

    await _process_user(bot, db, user_filter)

    bot.send_message.assert_called_once()
    call_kwargs = bot.send_message.call_args[1]
    assert "нет объявлений" in call_kwargs["text"]
    db.mark_empty_notified.assert_called_once_with(42)


@pytest.mark.asyncio
@patch("src.scheduler.monitor._aggregate_listings")
async def test_process_user_zero_matching_already_notified_no_send(
    mock_aggregate: AsyncMock,
) -> None:
    """_process_user: 0 matching, empty_notified_at уже установлен → уведомление не отправляется."""
    mock_aggregate.return_value = []
    bot = AsyncMock()
    db = AsyncMock()

    user_filter = UserFilter(
        user_id=42,
        cities=[1],
        initial_listings_count=5,
        is_active=True,
        empty_notified_at=1234567890.0,
    )

    await _process_user(bot, db, user_filter)

    bot.send_message.assert_not_called()
    db.mark_empty_notified.assert_not_called()
