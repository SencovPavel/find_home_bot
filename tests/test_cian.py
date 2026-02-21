"""Тесты парсера ЦИАН и защит от oversized payload."""

from __future__ import annotations

from src.parser.cian import (
    MAX_HTML_SIZE_BYTES,
    MAX_JSON_FRAGMENT_BYTES,
    parse_listings_from_html,
)


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
    assert listings[0].cian_id == 555
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
