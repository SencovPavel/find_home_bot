"""Парсер объявлений Яндекс Недвижимости: формирование URL, HTTP-запросы, извлечение данных."""

from __future__ import annotations

import json
import logging
import re
from typing import Dict, List
from urllib.parse import urlencode

import aiohttp
from bs4 import BeautifulSoup

from src.data.cities import get_city_by_id
from src.parser.base import fetch_page, parse_float
from src.parser.models import Listing, MetroTransport, Source, UserFilter

logger = logging.getLogger(__name__)

_BASE_URL = "https://realty.yandex.ru"

_RENOVATION_MAP: Dict[str, str] = {
    "косметический": "cosmetic",
    "евро": "euro",
    "евроремонт": "euro",
    "дизайнерский": "designer",
    "без ремонта": "no_renovation",
}

ROOMS_PARAM_MAP: Dict[int, str] = {
    0: "STUDIO",
    1: "1",
    2: "2",
    3: "3",
    4: "PLUS_4",
}


def build_search_url(
    user_filter: UserFilter,
    page: int = 1,
    *,
    city_slug: str | None = None,
) -> str:
    """Формирует URL поиска Яндекс Недвижимости для длительной аренды квартир.

    Если city_slug задан — используется он, иначе slug первого города из user_filter.cities.
    """
    if city_slug is None:
        city = get_city_by_id(user_filter.cities[0]) if user_filter.cities else None
        city_slug = city.slug if city else "moskva"
    base = f"{_BASE_URL}/{city_slug}/snyat/kvartira/"

    params: Dict[str, object] = {
        "sort": "DATE_DESC",
    }

    if user_filter.price_min:
        params["priceMin"] = user_filter.price_min
    if user_filter.price_max:
        params["priceMax"] = user_filter.price_max
    if user_filter.area_min:
        params["areaMin"] = int(user_filter.area_min)
    if user_filter.kitchen_area_min:
        params["kitchenSpaceMin"] = int(user_filter.kitchen_area_min)
    if user_filter.commission_max_percent == 0:
        params["hasAgentFee"] = "NO"

    if user_filter.rooms:
        room_values = []
        for r in user_filter.rooms:
            mapped = ROOMS_PARAM_MAP.get(r)
            if mapped:
                room_values.append(mapped)
        if room_values:
            params["roomsTotal"] = ",".join(room_values)

    if page > 1:
        params["page"] = page

    return f"{base}?{urlencode(params)}"


def _extract_json_data(soup: BeautifulSoup) -> dict | None:
    """Извлекает JSON из window.INITIAL_STATE на странице Яндекс Недвижимости."""
    for script in soup.find_all("script"):
        text = script.string or ""
        if "window.INITIAL_STATE" not in text:
            continue

        match = re.match(
            r"window\.INITIAL_STATE\s*=\s*(\{.*\})\s*;?\s*$",
            text,
            re.DOTALL,
        )
        if not match:
            continue

        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            logger.debug("Не удалось распарсить INITIAL_STATE Яндекс Недвижимости")
            continue

    return None


def _parse_from_json(data: dict) -> List[Listing]:
    """Парсит объявления из INITIAL_STATE Яндекс Недвижимости.

    Основной путь: data['search']['offers']['entities'].
    """
    listings: List[Listing] = []
    offers: list = []

    search = data.get("search")
    if isinstance(search, dict):
        search_offers = search.get("offers")
        if isinstance(search_offers, dict):
            offers = search_offers.get("entities", [])
        elif isinstance(search_offers, list):
            offers = search_offers

    if not offers:
        offers = data.get("offers") or data.get("snippets") or []

    for offer in offers:
        try:
            listing = _offer_to_listing(offer)
            if listing:
                listings.append(listing)
        except (KeyError, TypeError, ValueError) as exc:
            logger.debug("Не удалось распарсить Яндекс offer: %s", exc)
            continue

    return listings


def _offer_to_listing(offer: dict) -> Listing | None:
    """Преобразует JSON-объект из INITIAL_STATE Яндекс Недвижимости в Listing."""
    raw_id = offer.get("offerId") or offer.get("id")
    if not raw_id:
        return None

    try:
        listing_id = int(str(raw_id).replace("-", "")[:15])
    except (ValueError, TypeError):
        return None

    price_info = offer.get("price") or {}
    if isinstance(price_info, dict):
        price = int(price_info.get("value", 0))
    else:
        price = int(parse_float(price_info))

    commission = ""
    agent_fee = offer.get("agentFee")
    if agent_fee is not None:
        commission = "без комиссии" if str(agent_fee) == "0" else f"{agent_fee}%"
    elif offer.get("notForAgents") is True:
        commission = "без комиссии"

    location = offer.get("location") or {}
    address = location.get("address", "") or location.get("geocoderAddress", "")

    metro_station = ""
    metro_distance = 0
    metro_transport = MetroTransport.WALK
    metro_info = location.get("metro")
    if isinstance(metro_info, dict):
        metro_station = metro_info.get("name", "")
        metro_distance = int(metro_info.get("timeToMetro", 0))
        transport_type = metro_info.get("metroTransport", "ON_FOOT")
        if transport_type == "ON_TRANSPORT":
            metro_transport = MetroTransport.TRANSPORT

    area_info = offer.get("area") or {}
    total_area = parse_float(area_info.get("value") if isinstance(area_info, dict) else 0)
    kitchen_area = parse_float(offer.get("kitchenSpace") or offer.get("kitchenArea") or 0)

    rooms_key = offer.get("roomsTotalKey", "")
    rooms = _parse_rooms_key(rooms_key) if rooms_key else int(offer.get("roomsTotal") or 0)

    floors_offered = offer.get("floorsOffered")
    floor_val = int(floors_offered[0]) if isinstance(floors_offered, list) and floors_offered else 0
    total_floors = int(offer.get("floorsTotal") or 0)

    renovation_raw = (offer.get("renovation") or "").lower()
    renovation = _RENOVATION_MAP.get(renovation_raw, renovation_raw)

    description = offer.get("description", "")
    if offer.get("petsAllowed") is False:
        description = (description + " без животных").strip()

    photos: list[str] = []
    for img_url in (offer.get("appLargeImages") or offer.get("fullImages") or [])[:5]:
        if isinstance(img_url, str) and img_url:
            full = img_url if img_url.startswith("http") else f"https:{img_url}"
            photos.append(full)

    title = offer.get("title", "")
    if not title:
        room_label = "Студия" if rooms == 0 else f"{rooms}-комн. квартира"
        title = f"{room_label}, {total_area} м²"

    offer_url = offer.get("url") or f"{_BASE_URL}/offer/{raw_id}/"
    if offer_url.startswith("//"):
        offer_url = f"https:{offer_url}"
    elif offer_url.startswith("/"):
        offer_url = f"{_BASE_URL}{offer_url}"

    return Listing(
        listing_id=listing_id,
        source=Source.YANDEX,
        url=offer_url,
        title=title,
        price=price,
        address=address,
        metro_station=metro_station,
        metro_distance_min=metro_distance,
        metro_transport=metro_transport,
        total_area=total_area,
        kitchen_area=kitchen_area,
        rooms=rooms,
        floor=floor_val,
        total_floors=total_floors,
        renovation=renovation,
        description=description,
        commission=commission,
        photos=photos,
    )


def _parse_rooms_key(key: str) -> int:
    """Преобразует roomsTotalKey Яндекса (напр. '2', 'STUDIO', 'PLUS_4') в число комнат."""
    key_upper = key.upper()
    if key_upper == "STUDIO":
        return 0
    if key_upper == "PLUS_4":
        return 4
    try:
        return int(key)
    except ValueError:
        return 0


def _parse_from_html_cards(soup: BeautifulSoup) -> List[Listing]:
    """Fallback-парсинг из HTML-карточек Яндекс Недвижимости."""
    listings: List[Listing] = []

    cards = soup.select("[class*='OfferSnippet']") or soup.select("[class*='snippet']")

    for card in cards:
        try:
            link_tag = card.select_one("a[href*='/offer/']")
            if not link_tag:
                continue

            href = str(link_tag.get("href", ""))
            id_match = re.search(r"/offer/(\d+)", href)
            if not id_match:
                continue
            listing_id = int(id_match.group(1))

            title = link_tag.get_text(strip=True) or ""

            price_el = card.select_one("[class*='price']")
            price = 0
            if price_el:
                price = int(re.sub(r"[^\d]", "", price_el.get_text()) or 0)

            address_el = card.select_one("[class*='address']")
            address = address_el.get_text(strip=True) if address_el else ""

            metro_station = ""
            metro_el = card.select_one("[class*='metro']")
            if metro_el:
                metro_station = metro_el.get_text(strip=True)

            total_area = 0.0
            area_match = re.search(r"(\d+[.,]?\d*)\s*м", title)
            if area_match:
                total_area = float(area_match.group(1).replace(",", "."))

            rooms = 0
            rooms_match = re.search(r"(\d+)-комн", title)
            if rooms_match:
                rooms = int(rooms_match.group(1))

            url = href if href.startswith("http") else f"{_BASE_URL}{href}"

            listings.append(Listing(
                listing_id=listing_id,
                source=Source.YANDEX,
                url=url,
                title=title,
                price=price,
                address=address,
                metro_station=metro_station,
                metro_distance_min=0,
                metro_transport=MetroTransport.WALK,
                total_area=total_area,
                kitchen_area=0.0,
                rooms=rooms,
                floor=0,
                total_floors=0,
                renovation="",
                description="",
                commission="",
                photos=[],
            ))
        except (ValueError, AttributeError) as exc:
            logger.debug("Ошибка парсинга карточки Яндекс: %s", exc)
            continue

    return listings


def _unique_city_slugs(user_filter: UserFilter) -> List[str]:
    """Возвращает уникальные slug для выбранных городов."""
    seen: set[str] = set()
    result: List[str] = []
    for city_id in user_filter.cities or [1]:
        city = get_city_by_id(city_id)
        if city and city.slug not in seen:
            seen.add(city.slug)
            result.append(city.slug)
    return result if result else ["moskva"]


async def search_listings(
    user_filter: UserFilter,
    pages: int = 2,
) -> List[Listing]:
    """Выполняет поиск по Яндекс Недвижимости (по всем выбранным городам)."""
    all_listings: List[Listing] = []
    seen_ids: set[int] = set()
    slugs = _unique_city_slugs(user_filter)

    async with aiohttp.ClientSession() as session:
        for city_slug in slugs:
            for page in range(1, pages + 1):
                url = build_search_url(user_filter, page=page, city_slug=city_slug)
                logger.info("Запрос Яндекс Недвижимость (%s): %s", city_slug, url)

                html = await fetch_page(
                    session, url,
                    referer="https://realty.yandex.ru/",
                    delay_range=(2.0, 7.0),
                )
                if not html:
                    continue

                soup = BeautifulSoup(html, "lxml")

                json_data = _extract_json_data(soup)
                if json_data:
                    page_listings = _parse_from_json(json_data)
                else:
                    page_listings = _parse_from_html_cards(soup)

                for lst in page_listings:
                    if lst.listing_id not in seen_ids:
                        seen_ids.add(lst.listing_id)
                        all_listings.append(lst)
                logger.info("Яндекс %s стр.%d: найдено %d объявлений", city_slug, page, len(page_listings))

                if not page_listings:
                    break

    return all_listings
