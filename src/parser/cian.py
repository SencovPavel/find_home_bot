"""Парсер объявлений ЦИАН: формирование URL, HTTP-запросы, извлечение данных."""

from __future__ import annotations

import asyncio
import json
import logging
import random
import re
from typing import Sequence
from urllib.parse import urlencode

import aiohttp
from bs4 import BeautifulSoup

from src.parser.models import Listing, MetroTransport, UserFilter

logger = logging.getLogger(__name__)

_BASE_URL = "https://www.cian.ru/cat.php"
MAX_HTML_SIZE_BYTES = 5_000_000
MAX_SCRIPT_TEXT_BYTES = 1_000_000
MAX_JSON_FRAGMENT_BYTES = 1_000_000

_USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.2 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:134.0) Gecko/20100101 Firefox/134.0",
]

_RENOVATION_MAP: dict[str, str] = {
    "косметический": "cosmetic",
    "евроремонт": "euro",
    "дизайнерский": "designer",
    "без ремонта": "no_renovation",
}

CITY_REGION_MAP: dict[int, int] = {
    1: 1,   # Москва
    2: 2,   # Санкт-Петербург
}


def build_search_url(user_filter: UserFilter, page: int = 1) -> str:
    """Формирует URL поиска ЦИАН из пользовательских фильтров."""
    params: dict[str, str | int] = {
        "deal_type": "rent",
        "offer_type": "flat",
        "type": 4,  # длительная аренда
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

    if user_filter.rooms:
        for room_count in user_filter.rooms:
            key = f"room{room_count}"
            params[key] = 1

    return f"{_BASE_URL}?{urlencode(params)}"


def _get_headers() -> dict[str, str]:
    return {
        "User-Agent": random.choice(_USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Referer": "https://www.cian.ru/",
    }


async def fetch_page(session: aiohttp.ClientSession, url: str) -> str | None:
    """Загружает HTML-страницу с рандомной задержкой."""
    delay = random.uniform(2.0, 6.0)
    await asyncio.sleep(delay)

    try:
        async with session.get(url, headers=_get_headers(), timeout=aiohttp.ClientTimeout(total=30)) as resp:
            if resp.status != 200:
                logger.warning("ЦИАН вернул статус %d для %s", resp.status, url)
                return None
            content_length = resp.headers.get("Content-Length")
            if content_length and content_length.isdigit():
                if int(content_length) > MAX_HTML_SIZE_BYTES:
                    logger.warning(
                        "Слишком большой ответ ЦИАН (%s байт), запрос отклонён",
                        content_length,
                    )
                    return None
            body = await resp.text()
            if len(body.encode("utf-8")) > MAX_HTML_SIZE_BYTES:
                logger.warning("Слишком большой HTML-ответ (%d байт), пропускаем", len(body.encode("utf-8")))
                return None
            return body
    except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
        logger.error("Ошибка при запросе %s: %s", url, exc)
        return None


def parse_listings_from_html(html: str) -> list[Listing]:
    """Извлекает объявления из HTML-страницы ЦИАН.

    ЦИАН встраивает данные в JSON внутри тега <script> с ключом `initialState`
    или в виде JSON-LD. Парсим оба варианта.
    """
    listings: list[Listing] = []
    html_bytes = len(html.encode("utf-8"))
    if html_bytes > MAX_HTML_SIZE_BYTES:
        logger.warning("HTML превышает лимит (%d байт), парсинг остановлен", html_bytes)
        return listings

    soup = BeautifulSoup(html, "lxml")

    json_data = _extract_initial_state(soup)
    if json_data:
        listings.extend(_parse_from_json(json_data))
        return listings

    listings.extend(_parse_from_html_cards(soup))
    return listings


def _extract_initial_state(soup: BeautifulSoup) -> dict | None:
    """Ищет JSON с данными объявлений в <script> тегах страницы."""
    for script in soup.find_all("script"):
        text = script.string or ""
        if len(text.encode("utf-8")) > MAX_SCRIPT_TEXT_BYTES:
            continue
        if "._cianConfig" in text or "initialState" in text:
            match = re.search(r"window\._cianConfig\[.*?\]\s*=\s*(\{.*\})", text, re.DOTALL)
            if match:
                fragment = match.group(1)
                if len(fragment.encode("utf-8")) > MAX_JSON_FRAGMENT_BYTES:
                    logger.debug("JSON fragment _cianConfig превышает лимит, пропускаем")
                    continue
                try:
                    return json.loads(fragment)
                except json.JSONDecodeError:
                    continue

            match = re.search(r'"offersSerialized"\s*:\s*(\[.*?\])\s*[,}]', text, re.DOTALL)
            if match:
                fragment = match.group(1)
                if len(fragment.encode("utf-8")) > MAX_JSON_FRAGMENT_BYTES:
                    logger.debug("JSON fragment offersSerialized превышает лимит, пропускаем")
                    continue
                try:
                    return {"offers": json.loads(fragment)}
                except json.JSONDecodeError:
                    continue
    return None


def _parse_from_json(data: dict) -> list[Listing]:
    """Парсит объявления из JSON-структуры ЦИАН."""
    listings: list[Listing] = []

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
    cian_id = offer.get("cianId") or offer.get("id")
    if not cian_id:
        return None

    price_info = offer.get("bargainTerms") or offer.get("priceInfo") or {}
    price = int(price_info.get("price", 0) or price_info.get("priceRur", 0))

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

    total_area = _parse_float(offer.get("totalArea"))
    kitchen_area = _parse_float(offer.get("kitchenArea"))
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

    offer_url = offer.get("fullUrl", f"https://www.cian.ru/rent/flat/{cian_id}/")

    return Listing(
        cian_id=int(cian_id),
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
        photos=photos,
    )


def _parse_from_html_cards(soup: BeautifulSoup) -> list[Listing]:
    """Fallback-парсинг из HTML-карточек, если JSON недоступен."""
    listings: list[Listing] = []

    cards = soup.select("[data-name='GeneralInfoSectionRowComponent']")
    if not cards:
        cards = soup.select("article[data-name='CardComponent']")

    for card in cards:
        try:
            link_tag = card.select_one("a[href*='/rent/flat/']")
            if not link_tag:
                continue

            href = link_tag.get("href", "")
            cian_id_match = re.search(r"/flat/(\d+)/", href)
            if not cian_id_match:
                continue
            cian_id = int(cian_id_match.group(1))

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

            area_text = title
            total_area = 0.0
            area_match = re.search(r"(\d+[.,]?\d*)\s*м", area_text)
            if area_match:
                total_area = float(area_match.group(1).replace(",", "."))

            rooms = 0
            rooms_match = re.search(r"(\d+)-комн", title)
            if rooms_match:
                rooms = int(rooms_match.group(1))

            listings.append(Listing(
                cian_id=cian_id,
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
                photos=[],
            ))
        except (ValueError, AttributeError) as exc:
            logger.debug("Ошибка парсинга карточки: %s", exc)
            continue

    return listings


async def search_listings(
    user_filter: UserFilter,
    pages: int = 2,
) -> list[Listing]:
    """Выполняет поиск по ЦИАН и возвращает список объявлений."""
    all_listings: list[Listing] = []

    async with aiohttp.ClientSession() as session:
        for page in range(1, pages + 1):
            url = build_search_url(user_filter, page=page)
            logger.info("Запрос ЦИАН: %s", url)

            html = await fetch_page(session, url)
            if not html:
                continue

            page_listings = parse_listings_from_html(html)
            all_listings.extend(page_listings)
            logger.info("Страница %d: найдено %d объявлений", page, len(page_listings))

            if not page_listings:
                break

    return all_listings


def _parse_float(value: object) -> float:
    if value is None:
        return 0.0
    try:
        return float(str(value).replace(",", "."))
    except (ValueError, TypeError):
        return 0.0
