"""Тесты парсера ЦИАН и защит от oversized payload."""

from __future__ import annotations

from src.parser.cian import (
    MAX_HTML_SIZE_BYTES,
    MAX_JSON_FRAGMENT_BYTES,
    build_search_url,
    parse_listings_from_html,
)
from src.parser.models import UserFilter


def test_parse_listings_from_html_oversized_input_returns_empty() -> None:
    """Слишком большой HTML не парсится и возвращает пустой список."""
    oversized = "x" * (MAX_HTML_SIZE_BYTES + 1)

    listings = parse_listings_from_html(oversized)

    assert listings == []


def test_parse_listings_from_html_parses_offer_from_json_script() -> None:
    """Парсит объявление из script с offersSerialized."""
    html = """
    <html><body>
      <script>
        window._cianConfig["frontend-serp"] = {
          "offersSerialized": [{
            "id": 555,
            "title": "1-комн квартира",
            "priceInfo": {"price": 70000},
            "geo": {"address": [{"type":"street","fullName":"Тверская"}]},
            "roomsCount": 1,
            "totalArea": 35.5,
            "kitchenArea": 8.0,
            "floorNumber": 2,
            "building": {"floorsCount": 9}
          }]
        };
      </script>
    </body></html>
    """

    listings = parse_listings_from_html(html)

    assert len(listings) == 1
    assert listings[0].listing_id == 555
    assert listings[0].price == 70000


def test_parse_listings_skips_huge_json_fragment() -> None:
    """Игнорирует JSON-фрагмент, если он превышает лимит."""
    huge_fragment = "a" * (MAX_JSON_FRAGMENT_BYTES + 10)
    html = f"""
    <html><body>
      <script>
        window._cianConfig["frontend-serp"] = {{{huge_fragment}}};
      </script>
    </body></html>
    """

    listings = parse_listings_from_html(html)

    assert listings == []


def test_build_search_url_basic_params() -> None:
    """URL содержит обязательные параметры поиска."""
    user_filter = UserFilter(user_id=1, city=1, rooms=[2], price_max=100_000)

    url = build_search_url(user_filter, page=1)

    assert "deal_type=rent" in url
    assert "offer_type=flat" in url
    assert "region=1" in url
    assert "maxprice=100000" in url
    assert "room2=1" in url


def test_build_search_url_with_all_filters() -> None:
    """URL учитывает все фильтры пользователя."""
    user_filter = UserFilter(
        user_id=1,
        city=2,
        rooms=[1, 3],
        price_min=50_000,
        price_max=150_000,
        area_min=40.0,
        kitchen_area_min=8.0,
        no_commission=True,
    )

    url = build_search_url(user_filter, page=2)

    assert "region=2" in url
    assert "minprice=50000" in url
    assert "maxprice=150000" in url
    assert "mintarea=40" in url
    assert "minkarea=8" in url
    assert "is_by_homeowner=1" in url
    assert "room1=1" in url
    assert "room3=1" in url
    assert "p=2" in url


def test_parse_listings_from_html_cards_fallback() -> None:
    """Парсит объявления из HTML-карточек, если JSON недоступен."""
    html = """
    <html><body>
      <article data-name="CardComponent">
        <a href="https://www.cian.ru/rent/flat/999/">2-комн. 50 м²</a>
        <span data-mark="MainPrice">80 000 ₽/мес.</span>
        <div data-name="AddressItem">Москва, ул. Ленина</div>
      </article>
    </body></html>
    """

    listings = parse_listings_from_html(html)

    assert len(listings) == 1
    assert listings[0].listing_id == 999
    assert listings[0].price == 80000
    assert "Ленина" in listings[0].address


def test_parse_listings_from_html_empty_page() -> None:
    """Пустая страница без объявлений возвращает пустой список."""
    html = "<html><body><div>Ничего не найдено</div></body></html>"

    listings = parse_listings_from_html(html)

    assert listings == []


def test_parse_listings_json_with_cian_id_field() -> None:
    """Парсер использует cianId если он есть в JSON."""
    html = """
    <html><body>
      <script>
        window._cianConfig["frontend-serp"] = {
          "offersSerialized": [{
            "cianId": 777,
            "title": "Студия",
            "bargainTerms": {"price": 45000, "agentFee": "0"},
            "geo": {"address": []},
            "roomsCount": 0,
            "totalArea": 20,
            "kitchenArea": 5,
            "floorNumber": 1,
            "building": {"floorsCount": 5}
          }]
        };
      </script>
    </body></html>
    """

    listings = parse_listings_from_html(html)

    assert len(listings) == 1
    assert listings[0].listing_id == 777
    assert listings[0].commission == "без комиссии"


def test_parse_listings_json_with_metro_and_photos() -> None:
    """Парсер извлекает метро, фото и clientFee."""
    html = """
    <html><body>
      <script>
        window._cianConfig["frontend-serp"] = {
          "offersSerialized": [{
            "id": 888,
            "title": "2-комн квартира",
            "bargainTerms": {"price": 90000, "clientFee": "50"},
            "geo": {
              "address": [{"type":"street","fullName":"ул. Ленина"}],
              "undergrounds": [
                {"name": "Арбатская", "time": 5, "transportType": "walk"}
              ]
            },
            "roomsCount": 2,
            "totalArea": "55,5",
            "kitchenArea": 12,
            "floorNumber": 3,
            "building": {"floorsCount": 12},
            "repairType": "евроремонт",
            "description": "Уютная квартира",
            "photos": [
              {"fullUrl": "https://img.cian.ru/1.jpg"},
              {"thumbnailUrl": "https://img.cian.ru/2_thumb.jpg"}
            ]
          }]
        };
      </script>
    </body></html>
    """

    listings = parse_listings_from_html(html)

    assert len(listings) == 1
    listing = listings[0]
    assert listing.listing_id == 888
    assert listing.metro_station == "Арбатская"
    assert listing.metro_distance_min == 5
    assert listing.commission == "50%"
    assert len(listing.photos) == 2
    assert listing.renovation == "euro"
