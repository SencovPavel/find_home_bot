"""Тесты бизнес-фильтрации объявлений."""

from __future__ import annotations

from src.parser.models import (
    Listing,
    MetroTransport,
    Source,
    UserFilter,
    _parse_commission_percent,
)


def _listing_with_description(description: str) -> Listing:
    return Listing(
        listing_id=10,
        source=Source.CIAN,
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


def test_listing_has_pet_ban_in_title() -> None:
    """Объявление с «Без животных» только в title (description пустой) отклоняется при pets_allowed=True."""
    listing = _listing_with_description("")
    listing.title = "2-комн., 45 м², без животных"
    user_filter = UserFilter(user_id=1, pets_allowed=True)

    assert user_filter.matches(listing) is False


def test_user_filter_rejects_by_price_min() -> None:
    """Объявление дешевле price_min отклоняется."""
    listing = _listing_with_description("Квартира")
    listing.price = 30_000
    user_filter = UserFilter(user_id=1, price_min=50_000, pets_allowed=False)

    assert user_filter.matches(listing) is False


def test_user_filter_rejects_by_price_max() -> None:
    """Объявление дороже price_max отклоняется."""
    listing = _listing_with_description("Квартира")
    listing.price = 200_000
    user_filter = UserFilter(user_id=1, price_max=100_000, pets_allowed=False)

    assert user_filter.matches(listing) is False


def test_user_filter_rejects_by_area() -> None:
    """Объявление с маленькой площадью отклоняется."""
    listing = _listing_with_description("Квартира")
    listing.total_area = 25.0
    user_filter = UserFilter(user_id=1, area_min=40.0, pets_allowed=False)

    assert user_filter.matches(listing) is False


def test_user_filter_rejects_by_kitchen_area() -> None:
    """Объявление с маленькой кухней отклоняется."""
    listing = _listing_with_description("Квартира")
    listing.kitchen_area = 5.0
    user_filter = UserFilter(user_id=1, kitchen_area_min=8.0, pets_allowed=False)

    assert user_filter.matches(listing) is False


def test_user_filter_rejects_by_rooms() -> None:
    """Объявление с неподходящим числом комнат отклоняется."""
    listing = _listing_with_description("Квартира")
    listing.rooms = 3
    user_filter = UserFilter(user_id=1, rooms=[1, 2], pets_allowed=False)

    assert user_filter.matches(listing) is False


def test_user_filter_rejects_by_renovation() -> None:
    """Объявление с неподходящим типом ремонта отклоняется."""
    listing = _listing_with_description("Квартира")
    listing.renovation = "no_renovation"
    user_filter = UserFilter(user_id=1, renovation_types=["euro"], pets_allowed=False)

    assert user_filter.matches(listing) is False


def test_user_filter_rejects_by_commission() -> None:
    """Объявление с комиссией 50% отклоняется при commission_max_percent=0."""
    listing = _listing_with_description("Квартира")
    listing.commission = "50%"
    user_filter = UserFilter(user_id=1, commission_max_percent=0, pets_allowed=False)

    assert user_filter.matches(listing) is False


def test_user_filter_allows_no_commission_listing() -> None:
    """Объявление без комиссии проходит при commission_max_percent=0."""
    listing = _listing_with_description("Квартира")
    listing.commission = "без комиссии"
    user_filter = UserFilter(user_id=1, commission_max_percent=0, pets_allowed=False)

    assert user_filter.matches(listing) is True


def test_user_filter_allows_up_to_max_commission() -> None:
    """Объявление с комиссией 30% проходит при commission_max_percent=50."""
    listing = _listing_with_description("Квартира")
    listing.commission = "30%"
    user_filter = UserFilter(user_id=1, commission_max_percent=50, pets_allowed=False)

    assert user_filter.matches(listing) is True


def test_user_filter_rejects_over_max_commission() -> None:
    """Объявление с комиссией 50% отклоняется при commission_max_percent=30."""
    listing = _listing_with_description("Квартира")
    listing.commission = "50%"
    user_filter = UserFilter(user_id=1, commission_max_percent=30, pets_allowed=False)

    assert user_filter.matches(listing) is False


def test_user_filter_allows_zero_percent_commission() -> None:
    """Объявление с комиссией 0% проходит при commission_max_percent=0."""
    listing = _listing_with_description("Квартира")
    listing.commission = "0%"
    user_filter = UserFilter(user_id=1, commission_max_percent=0, pets_allowed=False)

    assert user_filter.matches(listing) is True


def test_matches_approx_returns_none_when_tolerance_zero() -> None:
    """При нулевом допуске matches_approx всегда возвращает None."""
    listing = _listing_with_description("Квартира")
    user_filter = UserFilter(user_id=1, tolerance_percent=0, pets_allowed=False)

    assert user_filter.matches_approx(listing) is None


def test_matches_approx_returns_none_when_rooms_mismatch() -> None:
    """Строгий критерий: несовпадение комнат — None даже при допуске."""
    listing = _listing_with_description("Квартира")
    listing.rooms = 3
    user_filter = UserFilter(user_id=1, rooms=[1], tolerance_percent=20, pets_allowed=False)

    assert user_filter.matches_approx(listing) is None


def test_matches_approx_returns_none_when_renovation_mismatch() -> None:
    """Строгий критерий: несовпадение ремонта — None даже при допуске."""
    listing = _listing_with_description("Квартира")
    listing.renovation = "no_renovation"
    user_filter = UserFilter(
        user_id=1, renovation_types=["euro"], tolerance_percent=20, pets_allowed=False,
    )

    assert user_filter.matches_approx(listing) is None


def test_matches_approx_returns_none_when_pet_ban_strict() -> None:
    """Строгий критерий: запрет животных — None даже при допуске."""
    listing = _listing_with_description("Сдается, без животных.")
    user_filter = UserFilter(user_id=1, tolerance_percent=20, pets_allowed=True)

    assert user_filter.matches_approx(listing) is None


def test_matches_approx_returns_none_when_commission_strict() -> None:
    """Строгий критерий: комиссия превышает лимит — None даже при допуске."""
    listing = _listing_with_description("Квартира")
    listing.commission = "50%"
    user_filter = UserFilter(
        user_id=1, commission_max_percent=0, tolerance_percent=20, pets_allowed=False,
    )

    assert user_filter.matches_approx(listing) is None


def test_matches_approx_price_over_within_tolerance() -> None:
    """Цена немного выше price_max — возвращает отклонение."""
    listing = _listing_with_description("Квартира")
    listing.price = 105_000
    user_filter = UserFilter(
        user_id=1, price_max=100_000, tolerance_percent=10, pets_allowed=False,
    )

    result = user_filter.matches_approx(listing)
    assert result is not None
    assert any("Цена выше" in d for d in result)


def test_matches_approx_price_over_exceeds_tolerance() -> None:
    """Цена значительно выше price_max — None."""
    listing = _listing_with_description("Квартира")
    listing.price = 150_000
    user_filter = UserFilter(
        user_id=1, price_max=100_000, tolerance_percent=10, pets_allowed=False,
    )

    assert user_filter.matches_approx(listing) is None


def test_matches_approx_price_under_within_tolerance() -> None:
    """Цена немного ниже price_min — возвращает отклонение."""
    listing = _listing_with_description("Квартира")
    listing.price = 48_000
    user_filter = UserFilter(
        user_id=1, price_min=50_000, tolerance_percent=10, pets_allowed=False,
    )

    result = user_filter.matches_approx(listing)
    assert result is not None
    assert any("Цена ниже" in d for d in result)


def test_matches_approx_area_under_within_tolerance() -> None:
    """Площадь немного меньше area_min — возвращает отклонение."""
    listing = _listing_with_description("Квартира")
    listing.total_area = 38.0
    user_filter = UserFilter(
        user_id=1, area_min=40.0, tolerance_percent=10, pets_allowed=False,
    )

    result = user_filter.matches_approx(listing)
    assert result is not None
    assert any("Площадь меньше" in d for d in result)


def test_matches_approx_area_under_exceeds_tolerance() -> None:
    """Площадь сильно меньше area_min — None."""
    listing = _listing_with_description("Квартира")
    listing.total_area = 20.0
    user_filter = UserFilter(
        user_id=1, area_min=40.0, tolerance_percent=10, pets_allowed=False,
    )

    assert user_filter.matches_approx(listing) is None


def test_matches_approx_kitchen_under_within_tolerance() -> None:
    """Кухня немного меньше kitchen_area_min — возвращает отклонение."""
    listing = _listing_with_description("Квартира")
    listing.kitchen_area = 7.5
    user_filter = UserFilter(
        user_id=1, kitchen_area_min=8.0, tolerance_percent=10, pets_allowed=False,
    )

    result = user_filter.matches_approx(listing)
    assert result is not None
    assert any("Кухня меньше" in d for d in result)


def test_matches_approx_kitchen_under_exceeds_tolerance() -> None:
    """Кухня сильно меньше — None."""
    listing = _listing_with_description("Квартира")
    listing.kitchen_area = 4.0
    user_filter = UserFilter(
        user_id=1, kitchen_area_min=8.0, tolerance_percent=10, pets_allowed=False,
    )

    assert user_filter.matches_approx(listing) is None


def test_matches_approx_returns_none_when_exact_match() -> None:
    """Если объявление точно подходит, deviations пусты — возвращает None."""
    listing = _listing_with_description("Квартира")
    user_filter = UserFilter(user_id=1, tolerance_percent=10, pets_allowed=False)

    assert user_filter.matches_approx(listing) is None


def test_matches_approx_price_under_exceeds_tolerance() -> None:
    """Цена значительно ниже price_min — None."""
    listing = _listing_with_description("Квартира")
    listing.price = 30_000
    user_filter = UserFilter(
        user_id=1, price_min=50_000, tolerance_percent=10, pets_allowed=False,
    )

    assert user_filter.matches_approx(listing) is None


def test_user_filter_passes_empty_commission_with_max_zero() -> None:
    """Пустая комиссия проходит при commission_max_percent=0 (трактуется как 0%)."""
    listing = _listing_with_description("Квартира")
    listing.commission = ""
    user_filter = UserFilter(user_id=1, commission_max_percent=0, pets_allowed=False)

    assert user_filter.matches(listing) is True


def test_parse_commission_percent_empty_returns_zero() -> None:
    """Пустая строка комиссии трактуется как 0%."""
    assert _parse_commission_percent("") == 0


def test_parse_commission_percent_zero_and_percent() -> None:
    """'0', '0%' → 0."""
    assert _parse_commission_percent("0") == 0
    assert _parse_commission_percent("0%") == 0


def test_parse_commission_percent_no_commission_markers() -> None:
    """'без комиссии', 'комиссия 0' → 0."""
    assert _parse_commission_percent("без комиссии") == 0
    assert _parse_commission_percent("комиссия 0") == 0


def test_parse_commission_percent_numeric() -> None:
    """Числовые значения парсятся корректно."""
    assert _parse_commission_percent("30%") == 30
    assert _parse_commission_percent("50%") == 50
    assert _parse_commission_percent("50") == 50
    assert _parse_commission_percent("100") == 100


def test_parse_commission_percent_invalid_returns_none() -> None:
    """Нераспознаваемый формат → None."""
    assert _parse_commission_percent("комиссия агента") is None
