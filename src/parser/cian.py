"""Парсер объявлений ЦИАН: формирование URL, HTTP-запросы, извлечение данных."""

from __future__ import annotations

import json
import logging
import re
from typing import Dict, List
from urllib.parse import urlencode

import aiohttp
from bs4 import BeautifulSoup

from src.parser.base import fetch_page, parse_float
from src.parser.models import Listing, MetroTransport, Source, UserFilter

logger = logging.getLogger(__name__)

_BASE_URL = "https://www.cian.ru/cat.php"

_RENOVATION_MAP: Dict[str, str] = {
    "косметический": "cosmetic",
    "евроремонт": "euro",
    "дизайнерский": "designer",
    "без ремонта": "no_renovation",
}

CITY_REGION_MAP: Dict[int, int] = {
    1: 1,
    2: 2,
}


def build_search_url(user_filter: UserFilter, page: int = 1) -> str:
    """Формирует URL поиска ЦИАН из пользовательских фильтров."""
    params: dict[str, object] = {
        "deal_type": "rent",
        "offer_type": "flat",
        "type": 4,
        "region": CITY_REGION_MAP.get(user_filter.city, user_filter.city),
        "p": page,
        "sort": "creation_date_desc",
    }

    if user_filter.price_min:
        params["minprice"] = user_filter.price_min
    if user_filter.price_max:
        params["maxprice"] = user_filter.price_max
    if user_filter.area_min:
        params["mintarea"] = int(user_filter.area_min)
    if user_filter.kitchen_area_min:
        params["minkarea"] = int(user_filter.kitchen_area_min)
    if user_filter.no_commission:
        params["is_by_homeowner"] = 1

    if user_filter.rooms:
        for room_count in user_filter.rooms:
            params[f"room{room_count}"] = 1

    return f"{_BASE_URL}?{urlencode(params)}"


def parse_listings_from_html(html: str) -> List[Listing]:
    """Извлекает объявления из HTML-страницы ЦИАН."""
    soup = BeautifulSoup(html, "lxml")

    json_data = _extract_initial_state(soup)
    if json_data:
        listings = _parse_from_json(json_data)
        if listings:
            return listings

    return _parse_from_html_cards(soup)


def _extract_initial_state(soup: BeautifulSoup) -> dict | None:
    """Извлекает JSON с объявлениями из _cianConfig['frontend-serp'].

    ЦИАН хранит данные в формате:
    window._cianConfig['frontend-serp'] = (...).concat([{key: 'initialState', value: {...}}, ...])
    Реальные объявления лежат в initialState.results.offers.
    """
    for script in soup.find_all("script"):
        text = script.string or ""
        if not text.lstrip().startswith("window._cianConfig"):
            continue
        if "'frontend-serp'" not in text and '"frontend-serp"' not in text:
            continue

        match = re.search(r"\.concat\((\[.+\])\)\s*;?\s*$", text, re.DOTALL)
        if not match:
            continue

        try:
            config_items = json.loads(match.group(1))
        except json.JSONDecodeError:
            logger.debug("Не удалось распарсить concat-массив frontend-serp")
            continue

        for item in config_items:
            if not isinstance(item, dict) or item.get("key") != "initialState":
                continue
            state = item.get("value")
            if isinstance(state, dict) and isinstance(state.get("results"), dict):
                return state

    return None


def _parse_from_json(data: dict) -> List[Listing]:
    """Парсит объявления из JSON-структуры ЦИАН."""
    listings: List[Listing] = []

    offers = data.get("offers") or data.get("offersSerialized") or []

    if isinstance(data.get("results"), dict):
        offers = data["results"].get("offers", [])

    for offer in offers:
        try:
            listing = _offer_to_listing(offer)
            if listing:
                listings.append(listing)
        except (KeyError, TypeError, ValueError) as exc:
            logger.debug("Не удалось распарсить offer: %s", exc)
            continue

    return listings


def _offer_to_listing(offer: dict) -> Listing | None:
    """Преобразует JSON-объект offer в Listing."""
    raw_id = offer.get("cianId") or offer.get("id")
    if not raw_id:
        return None

    price_info = offer.get("bargainTerms") or offer.get("priceInfo") or {}
    price = int(price_info.get("price", 0) or price_info.get("priceRur", 0))

    commission = ""
    agent_fee = price_info.get("agentFee")
    if agent_fee is not None:
        commission = "без комиссии" if str(agent_fee) == "0" else f"{agent_fee}%"
    elif price_info.get("clientFee") is not None:
        client_fee = str(price_info["clientFee"])
        commission = "без комиссии" if client_fee == "0" else f"{client_fee}%"

    geo = offer.get("geo") or {}
    address_parts: list[str] = []
    for addr in geo.get("address", []):
        if addr.get("type") in ("location", "street", "house"):
            address_parts.append(addr.get("fullName", ""))
    address = ", ".join(address_parts) if address_parts else ""

    metro_station = ""
    metro_distance = 0
    metro_transport = MetroTransport.WALK
    undergrounds = geo.get("undergrounds") or []
    if undergrounds:
        nearest = undergrounds[0]
        metro_station = nearest.get("name", "")
        metro_distance = nearest.get("time", 0)
        transport_type = nearest.get("transportType", "walk")
        metro_transport = MetroTransport.TRANSPORT if transport_type == "transport" else MetroTransport.WALK

    total_area = parse_float(offer.get("totalArea"))
    kitchen_area = parse_float(offer.get("kitchenArea"))
    rooms = int(offer.get("roomsCount", 0))
    floor = int(offer.get("floorNumber", 0))

    building = offer.get("building") or {}
    total_floors = int(building.get("floorsCount", 0))

    renovation_raw = (offer.get("repairType") or "").lower()
    renovation = _RENOVATION_MAP.get(renovation_raw, renovation_raw)

    description = offer.get("description", "")

    photos: list[str] = []
    for photo in (offer.get("photos") or [])[:5]:
        url = photo.get("fullUrl") or photo.get("thumbnailUrl") or ""
        if url:
            photos.append(url)

    offer_url = offer.get("fullUrl", f"https://www.cian.ru/rent/flat/{raw_id}/")

    return Listing(
        listing_id=int(raw_id),
        source=Source.CIAN,
        url=offer_url,
        title=offer.get("title", f"{rooms}-комн. квартира, {total_area} м²"),
        price=price,
        address=address,
        metro_station=metro_station,
        metro_distance_min=metro_distance,
        metro_transport=metro_transport,
        total_area=total_area,
        kitchen_area=kitchen_area,
        rooms=rooms,
        floor=floor,
        total_floors=total_floors,
        renovation=renovation,
        description=description,
        commission=commission,
        photos=photos,
    )


def _parse_from_html_cards(soup: BeautifulSoup) -> List[Listing]:
    """Fallback-парсинг из HTML-карточек, если JSON недоступен."""
    listings: List[Listing] = []

    cards = soup.select("[data-name='GeneralInfoSectionRowComponent']")
    if not cards:
        cards = soup.select("article[data-name='CardComponent']")

    for card in cards:
        try:
            link_tag = card.select_one("a[href*='/rent/flat/']")
            if not link_tag:
                continue

            href = link_tag.get("href", "")
            id_match = re.search(r"/flat/(\d+)/", href)
            if not id_match:
                continue
            listing_id = int(id_match.group(1))

            title = link_tag.get_text(strip=True) or ""

            price_el = card.select_one("[data-mark='MainPrice']")
            price_text = price_el.get_text(strip=True) if price_el else "0"
            price = int(re.sub(r"[^\d]", "", price_text) or 0)

            address_el = card.select_one("[data-name='AddressItem']")
            address = address_el.get_text(strip=True) if address_el else ""

            metro_station = ""
            metro_distance = 0
            metro_transport = MetroTransport.WALK
            metro_el = card.select_one("[data-name='UndergroundItem']")
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

            listings.append(Listing(
                listing_id=listing_id,
                source=Source.CIAN,
                url=str(href),
                title=title,
                price=price,
                address=address,
                metro_station=metro_station,
                metro_distance_min=metro_distance,
                metro_transport=metro_transport,
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
            logger.debug("Ошибка парсинга карточки ЦИАН: %s", exc)
            continue

    return listings


async def search_listings(
    user_filter: UserFilter,
    pages: int = 2,
) -> List[Listing]:
    """Выполняет поиск по ЦИАН и возвращает список объявлений."""
    all_listings: List[Listing] = []

    async with aiohttp.ClientSession() as session:
        for page in range(1, pages + 1):
            url = build_search_url(user_filter, page=page)
            logger.info("Запрос ЦИАН: %s", url)

            html = await fetch_page(session, url, referer="https://www.cian.ru/")
            if not html:
                continue

            page_listings = parse_listings_from_html(html)
            all_listings.extend(page_listings)
            logger.info("ЦИАН страница %d: найдено %d объявлений", page, len(page_listings))

            if not page_listings:
                break

    return all_listings
