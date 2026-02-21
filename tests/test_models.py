"""Тесты бизнес-фильтрации объявлений."""

from __future__ import annotations

from src.parser.models import Listing, MetroTransport, UserFilter


def _listing_with_description(description: str) -> Listing:
    return Listing(
        cian_id=10,
        url="https://www.cian.ru/rent/flat/10/",
        title="2-комн квартира",
        price=80_000,
        address="Москва",
        metro_station="",
        metro_distance_min=0,
        metro_transport=MetroTransport.WALK,
        total_area=45.0,
        kitchen_area=10.0,
        rooms=2,
        floor=5,
        total_floors=10,
        renovation="euro",
        description=description,
        photos=[],
    )


def test_user_filter_matches_positive_case() -> None:
    """Совпадение по всем параметрам возвращает True."""
    listing = _listing_with_description("Квартира в хорошем состоянии")
    user_filter = UserFilter(
        user_id=1,
        price_min=60_000,
        price_max=100_000,
        area_min=40.0,
        kitchen_area_min=8.0,
        rooms=[2],
        renovation_types=["euro"],
        pets_allowed=False,
    )

    assert user_filter.matches(listing) is True


def test_user_filter_rejects_pet_ban_when_pets_allowed_true() -> None:
    """Если включен фильтр животных, объявления с запретом отклоняются."""
    listing = _listing_with_description("Сдается, без животных.")
    user_filter = UserFilter(user_id=1, pets_allowed=True)

    assert user_filter.matches(listing) is False


def test_user_filter_allows_pet_ban_when_pets_filter_disabled() -> None:
    """Если фильтр животных отключен, объявление допускается."""
    listing = _listing_with_description("Без кошек и собак")
    user_filter = UserFilter(user_id=1, pets_allowed=False)

    assert user_filter.matches(listing) is True
