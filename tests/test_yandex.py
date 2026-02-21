"""Тесты парсера Яндекс Недвижимости: извлечение данных, URL, _parse_rooms_key."""

from __future__ import annotations

import json

from src.parser.models import MetroTransport, Source, UserFilter
from src.parser.yandex_realty import (
    _extract_json_data,
    _offer_to_listing,
    _parse_from_json,
    _parse_rooms_key,
    build_search_url,
)
from bs4 import BeautifulSoup


def _make_yandex_html(initial_state: dict) -> str:
    """Оборачивает dict в HTML с window.INITIAL_STATE."""
    state_json = json.dumps(initial_state)
    return (
        f"<html><body>"
        f"<script>window.INITIAL_STATE = {state_json};</script>"
        f"</body></html>"
    )


def _make_offer(**overrides: object) -> dict:
    """Формирует минимальный JSON-объект offer Яндекс Недвижимости."""
    base = {
        "offerId": "12345678",
        "price": {"value": 80000},
        "location": {
            "address": "Москва, ул. Тверская, 10",
            "metro": {
                "name": "Тверская",
                "timeToMetro": 5,
                "metroTransport": "ON_FOOT",
            },
        },
        "area": {"value": 45.0},
        "kitchenSpace": 10.0,
        "roomsTotalKey": "2",
        "floorsOffered": [5],
        "floorsTotal": 12,
        "renovation": "евроремонт",
        "description": "Уютная квартира",
        "appLargeImages": ["https://img.yandex.ru/1.jpg"],
    }
    base.update(overrides)
    return base


def test_extract_json_data_finds_initial_state() -> None:
    """Извлекает INITIAL_STATE из script-тега."""
    state = {"search": {"offers": {"entities": []}}}
    html = _make_yandex_html(state)
    soup = BeautifulSoup(html, "lxml")

    result = _extract_json_data(soup)

    assert result is not None
    assert "search" in result


def test_extract_json_data_returns_none_for_empty_page() -> None:
    """Возвращает None, если INITIAL_STATE отсутствует."""
    soup = BeautifulSoup("<html><body></body></html>", "lxml")

    assert _extract_json_data(soup) is None


def test_parse_from_json_extracts_offers() -> None:
    """Парсит объявления из search.offers.entities."""
    data = {
        "search": {
            "offers": {
                "entities": [_make_offer()],
            },
        },
    }

    listings = _parse_from_json(data)

    assert len(listings) == 1
    assert listings[0].price == 80000
    assert listings[0].source == Source.YANDEX


def test_parse_from_json_handles_list_offers() -> None:
    """Парсит объявления, если search.offers — список."""
    data = {"search": {"offers": [_make_offer()]}}

    listings = _parse_from_json(data)

    assert len(listings) == 1


def test_parse_from_json_empty_offers() -> None:
    """Пустой search.offers возвращает пустой список."""
    data = {"search": {"offers": {"entities": []}}}

    assert _parse_from_json(data) == []


def test_offer_to_listing_full_data() -> None:
    """Корректно извлекает все поля из полного offer."""
    offer = _make_offer()

    listing = _offer_to_listing(offer)

    assert listing is not None
    assert listing.listing_id == 12345678
    assert listing.price == 80000
    assert listing.total_area == 45.0
    assert listing.kitchen_area == 10.0
    assert listing.rooms == 2
    assert listing.floor == 5
    assert listing.total_floors == 12
    assert listing.renovation == "euro"
    assert listing.metro_station == "Тверская"
    assert listing.metro_distance_min == 5
    assert listing.metro_transport == MetroTransport.WALK
    assert len(listing.photos) == 1


def test_offer_to_listing_transport_type() -> None:
    """Распознаёт ON_TRANSPORT как MetroTransport.TRANSPORT."""
    offer = _make_offer(
        location={
            "address": "Адрес",
            "metro": {
                "name": "Речной вокзал",
                "timeToMetro": 15,
                "metroTransport": "ON_TRANSPORT",
            },
        },
    )

    listing = _offer_to_listing(offer)

    assert listing is not None
    assert listing.metro_transport == MetroTransport.TRANSPORT
    assert listing.metro_distance_min == 15


def test_offer_to_listing_without_metro() -> None:
    """Offer без метро создаёт listing с пустой станцией."""
    offer = _make_offer(location={"address": "Далёкий адрес"})

    listing = _offer_to_listing(offer)

    assert listing is not None
    assert listing.metro_station == ""
    assert listing.metro_distance_min == 0


def test_offer_to_listing_agent_fee_zero() -> None:
    """agentFee=0 распознаётся как 'без комиссии'."""
    offer = _make_offer(agentFee="0")

    listing = _offer_to_listing(offer)

    assert listing is not None
    assert listing.commission == "без комиссии"


def test_offer_to_listing_agent_fee_nonzero() -> None:
    """Ненулевая agentFee отображается как процент."""
    offer = _make_offer(agentFee="50")

    listing = _offer_to_listing(offer)

    assert listing is not None
    assert listing.commission == "50%"


def test_offer_to_listing_not_for_agents() -> None:
    """notForAgents=True при отсутствии agentFee -> 'без комиссии'."""
    offer = _make_offer(notForAgents=True)

    listing = _offer_to_listing(offer)

    assert listing is not None
    assert listing.commission == "без комиссии"


def test_offer_to_listing_no_id_returns_none() -> None:
    """Offer без offerId и id возвращает None."""
    offer = _make_offer()
    del offer["offerId"]

    assert _offer_to_listing(offer) is None


def test_offer_to_listing_price_as_scalar() -> None:
    """Если price — число, а не dict, парсер его обрабатывает."""
    offer = _make_offer(price=65000)

    listing = _offer_to_listing(offer)

    assert listing is not None
    assert listing.price == 65000


def test_offer_to_listing_studio() -> None:
    """roomsTotalKey='STUDIO' -> rooms=0."""
    offer = _make_offer(roomsTotalKey="STUDIO")

    listing = _offer_to_listing(offer)

    assert listing is not None
    assert listing.rooms == 0


def test_offer_to_listing_generates_title_if_missing() -> None:
    """При отсутствии title генерирует заголовок из rooms и area."""
    offer = _make_offer(roomsTotalKey="3")

    listing = _offer_to_listing(offer)

    assert listing is not None
    assert "3-комн." in listing.title
    assert "45.0 м²" in listing.title


def test_parse_rooms_key_numeric() -> None:
    """Числовые ключи корректно преобразуются."""
    assert _parse_rooms_key("1") == 1
    assert _parse_rooms_key("2") == 2
    assert _parse_rooms_key("3") == 3


def test_parse_rooms_key_studio() -> None:
    """STUDIO -> 0."""
    assert _parse_rooms_key("STUDIO") == 0
    assert _parse_rooms_key("studio") == 0


def test_parse_rooms_key_plus_4() -> None:
    """PLUS_4 -> 4."""
    assert _parse_rooms_key("PLUS_4") == 4
    assert _parse_rooms_key("plus_4") == 4


def test_parse_rooms_key_unknown() -> None:
    """Неизвестный ключ возвращает 0."""
    assert _parse_rooms_key("UNKNOWN") == 0


def test_build_search_url_moscow() -> None:
    """URL для Москвы содержит правильный slug и параметры."""
    user_filter = UserFilter(user_id=1, cities=[1], rooms=[2], price_max=100_000)

    url = build_search_url(user_filter, page=1)

    assert "/moskva/snyat/kvartira/" in url
    assert "priceMax=100000" in url
    assert "roomsTotal=2" in url
    assert "sort=DATE_DESC" in url


def test_build_search_url_spb() -> None:
    """URL для СПб содержит правильный slug."""
    user_filter = UserFilter(user_id=1, cities=[2])

    url = build_search_url(user_filter, page=1)

    assert "/sankt-peterburg/snyat/kvartira/" in url


def test_build_search_url_no_commission() -> None:
    """При commission_max_percent=0 добавляется hasAgentFee=NO."""
    user_filter = UserFilter(user_id=1, cities=[1], commission_max_percent=0)

    url = build_search_url(user_filter, page=1)

    assert "hasAgentFee=NO" in url


def test_build_search_url_all_filters() -> None:
    """URL учитывает все фильтры пользователя."""
    user_filter = UserFilter(
        user_id=1,
        cities=[1],
        rooms=[1, 3],
        price_min=40_000,
        price_max=120_000,
        area_min=35.0,
        kitchen_area_min=7.0,
        commission_max_percent=0,
    )

    url = build_search_url(user_filter, page=3)

    assert "priceMin=40000" in url
    assert "priceMax=120000" in url
    assert "areaMin=35" in url
    assert "kitchenSpaceMin=7" in url
    assert "page=3" in url


def test_build_search_url_page_1_no_page_param() -> None:
    """На первой странице параметр page не добавляется."""
    user_filter = UserFilter(user_id=1, cities=[1])

    url = build_search_url(user_filter, page=1)

    assert "page=" not in url


def test_build_search_url_rooms_multiple() -> None:
    """Несколько типов комнат объединяются через запятую."""
    user_filter = UserFilter(user_id=1, cities=[1], rooms=[1, 2, 3])

    url = build_search_url(user_filter, page=1)

    assert "roomsTotal=" in url
    parts = url.split("roomsTotal=")[1].split("&")[0]
    assert "1" in parts
    assert "2" in parts
    assert "3" in parts
