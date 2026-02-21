"""Парсер объявлений Яндекс Недвижимости: формирование URL, HTTP-запросы, извлечение данных."""

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

_BASE_URL = "https://realty.ya.ru"

CITY_SLUG_MAP: Dict[int, str] = {
    1: "moskva",
    2: "sankt-peterburg",
}

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


def build_search_url(user_filter: UserFilter, page: int = 1) -> str:
    """Формирует URL поиска Яндекс Недвижимости для длительной аренды квартир."""
    city_slug = CITY_SLUG_MAP.get(user_filter.city, "moskva")
    base = f"{_BASE_URL}/{city_slug}/snyat/kvartira/dlitelnaya-arenda/"

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
    if user_filter.no_commission:
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
    """Извлекает JSON с данными объявлений из HTML Яндекс Недвижимости."""
    for script in soup.find_all("script"):
        text = script.string or ""

        if "__realty_data__" in text or "initialState" in text:
            match = re.search(
                r"(?:window\.__realty_data__|window\.__initialState__)\s*=\s*(\{.*?\});\s*(?:</|$|\n)",
                text,
                re.DOTALL,
            )
            if match:
                try:
                    return json.loads(match.group(1))
                except json.JSONDecodeError:
                    pass

        if '"offers"' in text or '"snippets"' in text:
            match = re.search(r'"(?:offers|snippets)"\s*:\s*(\[.*?\])\s*[,}]', text, re.DOTALL)
            if match:
                try:
                    return {"offers": json.loads(match.group(1))}
                except json.JSONDecodeError:
                    pass

    ld_scripts = soup.find_all("script", {"type": "application/ld+json"})
    for ld in ld_scripts:
        try:
            data = json.loads(ld.string or "")
            if isinstance(data, dict) and data.get("@type") == "ItemList":
                return data
        except json.JSONDecodeError:
            continue

    return None


def _parse_from_json(data: dict) -> List[Listing]:
    """Парсит объявления из JSON-данных Яндекс Недвижимости."""
    listings: List[Listing] = []

    offers = data.get("offers") or data.get("snippets") or []

    if isinstance(data.get("search"), dict):
        offers = data["search"].get("offers", [])

    if isinstance(data.get("itemListElement"), list):
        offers = data["itemListElement"]

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
    """Преобразует JSON-объект Яндекс Недвижимости в Listing."""
    raw_id = offer.get("offerId") or offer.get("id") or offer.get("offerID")
    if not raw_id:
        return None

    try:
        listing_id = int(str(raw_id).replace("-", "")[:15])
    except (ValueError, TypeError):
        return None

    price_info = offer.get("price") or offer.get("priceInfo") or {}
    if isinstance(price_info, dict):
        price = int(price_info.get("value", 0) or price_info.get("rur", 0))
    else:
        price = int(parse_float(price_info))

    commission = ""
    agent_fee = offer.get("agentFee")
    if agent_fee is not None:
        commission = "без комиссии" if str(agent_fee) == "0" else f"{agent_fee}%"
    elif offer.get("hasAgentFee") is False:
        commission = "без комиссии"
    elif offer.get("commissioningType") == "noAgent":
        commission = "без комиссии"

    location = offer.get("location") or offer.get("geo") or {}
    address_parts: list[str] = []
    if isinstance(location.get("address"), str):
        address_parts.append(location["address"])
    elif isinstance(location.get("geocoderAddress"), str):
        address_parts.append(location["geocoderAddress"])
    else:
        for comp in location.get("addressComponents") or location.get("address", []):
            if isinstance(comp, dict):
                address_parts.append(comp.get("value", "") or comp.get("name", ""))
    address = ", ".join(p for p in address_parts if p)

    metro_station = ""
    metro_distance = 0
    metro_transport = MetroTransport.WALK
    metros = location.get("metro") or location.get("stations") or offer.get("metro") or []
    if isinstance(metros, list) and metros:
        nearest = metros[0]
        metro_station = nearest.get("name", "") or nearest.get("stationName", "")
        metro_distance = int(nearest.get("timeOnFoot", 0) or nearest.get("time", 0))
        if nearest.get("timeOnTransport") and not nearest.get("timeOnFoot"):
            metro_distance = int(nearest["timeOnTransport"])
            metro_transport = MetroTransport.TRANSPORT
    elif isinstance(metros, dict):
        metro_station = metros.get("name", "")
        metro_distance = int(metros.get("timeOnFoot", 0) or metros.get("time", 0))

    area_info = offer.get("area") or {}
    total_area = parse_float(area_info.get("value") if isinstance(area_info, dict) else offer.get("totalArea"))
    kitchen_area = parse_float(offer.get("kitchenSpace") or offer.get("kitchenArea"))
    rooms = int(offer.get("roomsTotal") or offer.get("roomsCount") or 0)
    floor_val = int(offer.get("floorsOffered", [0])[0] if isinstance(offer.get("floorsOffered"), list) else offer.get("floor", 0))
    total_floors = int(offer.get("floorsTotal") or 0)

    renovation_raw = (offer.get("renovation") or offer.get("repairType") or "").lower()
    renovation = _RENOVATION_MAP.get(renovation_raw, renovation_raw)

    description = offer.get("description", "")

    photos: list[str] = []
    for photo in (offer.get("images") or offer.get("photos") or [])[:5]:
        url = ""
        if isinstance(photo, str):
            url = photo
        elif isinstance(photo, dict):
            url = photo.get("appMiddle") or photo.get("full") or photo.get("url") or ""
        if url:
            photos.append(url)

    title = offer.get("title", "")
    if not title:
        title = f"{rooms}-комн. квартира, {total_area} м²"

    offer_url = offer.get("url") or offer.get("fullUrl") or f"{_BASE_URL}/offer/{raw_id}/"
    if offer_url.startswith("/"):
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


async def search_listings(
    user_filter: UserFilter,
    pages: int = 2,
) -> List[Listing]:
    """Выполняет поиск по Яндекс Недвижимости и возвращает список объявлений."""
    all_listings: List[Listing] = []

    async with aiohttp.ClientSession() as session:
        for page in range(1, pages + 1):
            url = build_search_url(user_filter, page=page)
            logger.info("Запрос Яндекс Недвижимость: %s", url)

            html = await fetch_page(
                session, url,
                referer="https://realty.ya.ru/",
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

            all_listings.extend(page_listings)
            logger.info("Яндекс страница %d: найдено %d объявлений", page, len(page_listings))

            if not page_listings:
                break

    return all_listings
