"""Парсер объявлений Авито: формирование URL, HTTP-запросы, извлечение данных."""

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

_RENOVATION_MAP: Dict[str, str] = {
    "косметический": "cosmetic",
    "евро": "euro",
    "евроремонт": "euro",
    "дизайнерский": "designer",
    "без ремонта": "no_renovation",
}


def build_search_url(
    user_filter: UserFilter,
    page: int = 1,
    *,
    city_slug: str | None = None,
) -> str:
    """Формирует URL поиска Авито для длительной аренды квартир.

    Если city_slug задан — используется он, иначе slug первого города из user_filter.cities.
    """
    if city_slug is None:
        city = get_city_by_id(user_filter.cities[0]) if user_filter.cities else None
        city_slug = city.slug if city else "moskva"
    base = f"https://www.avito.ru/{city_slug}/kvartiry/sdam/na_dlitelnyy_srok"

    params: Dict[str, object] = {}

    if user_filter.price_min:
        params["pmin"] = user_filter.price_min
    if user_filter.price_max:
        params["pmax"] = user_filter.price_max

    if page > 1:
        params["p"] = page

    if user_filter.commission_max_percent == 0:
        params["f"] = "ASgBAgICAkSSA8gQ8AeQUg"

    return f"{base}?{urlencode(params)}" if params else base


def _extract_json_data(soup: BeautifulSoup) -> dict | None:
    """Извлекает JSON с данными объявлений из HTML Авито."""
    for script in soup.find_all("script"):
        text = script.string or ""
        if "window.__initialData__" in text:
            match = re.search(
                r"window\.__initialData__\s*=\s*\"(.+?)\";\s*\n",
                text,
                re.DOTALL,
            )
            if match:
                try:
                    raw = match.group(1).encode().decode("unicode_escape")
                    return json.loads(raw)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    pass

        if "__state" in text:
            match = re.search(r'"items"\s*:\s*(\[.*?\])\s*[,}]', text, re.DOTALL)
            if match:
                try:
                    return {"items": json.loads(match.group(1))}
                except json.JSONDecodeError:
                    pass
    return None


def _parse_from_json(data: dict) -> List[Listing]:
    """Парсит объявления из JSON-данных Авито."""
    listings: List[Listing] = []

    items = data.get("items") or []
    if not items and isinstance(data.get("catalog"), dict):
        items = data["catalog"].get("items", [])

    for item in items:
        try:
            listing = _item_to_listing(item)
            if listing:
                listings.append(listing)
        except (KeyError, TypeError, ValueError) as exc:
            logger.debug("Не удалось распарсить Авито item: %s", exc)
            continue

    return listings


def _item_to_listing(item: dict) -> Listing | None:
    """Преобразует JSON-объект Авито в Listing."""
    item_id = item.get("id") or item.get("itemId")
    if not item_id:
        return None

    price = int(item.get("priceDetailed", {}).get("value", 0) or item.get("price", 0))
    title = item.get("title", "")

    location = item.get("location") or item.get("geo") or {}
    address = location.get("name", "") or location.get("address", "")

    metro_station = ""
    metro_distance = 0
    metro_transport = MetroTransport.WALK
    metro_info = location.get("metro") or {}
    if isinstance(metro_info, dict):
        metro_station = metro_info.get("name", "")
        metro_distance = int(metro_info.get("time", 0))
        if metro_info.get("type") == "transport":
            metro_transport = MetroTransport.TRANSPORT

    params = item.get("parameters") or item.get("params") or []
    total_area = 0.0
    kitchen_area = 0.0
    rooms = 0
    floor_val = 0
    total_floors = 0
    renovation = ""

    for param in params:
        label = (param.get("label") or param.get("name") or "").lower()
        value = str(param.get("value", ""))

        if "общая" in label or "площадь" in label:
            total_area = parse_float(re.sub(r"[^\d.,]", "", value))
        elif "кухн" in label:
            kitchen_area = parse_float(re.sub(r"[^\d.,]", "", value))
        elif "комнат" in label:
            rooms = int(re.sub(r"[^\d]", "", value) or 0)
        elif "этаж" in label:
            floor_match = re.match(r"(\d+)\s*(?:из|/)\s*(\d+)", value)
            if floor_match:
                floor_val = int(floor_match.group(1))
                total_floors = int(floor_match.group(2))
        elif "ремонт" in label:
            renovation = _RENOVATION_MAP.get(value.lower().strip(), value.lower().strip())

    if not total_area:
        area_match = re.search(r"(\d+[.,]?\d*)\s*м", title)
        if area_match:
            total_area = float(area_match.group(1).replace(",", "."))
    if not rooms:
        rooms_match = re.search(r"(\d+)-комн", title)
        if rooms_match:
            rooms = int(rooms_match.group(1))

    description = item.get("description", "")

    commission = ""
    badge_text = " ".join(
        str(b.get("title", "") or b.get("text", ""))
        for b in (item.get("badges") or [])
    ).lower()
    if "без комиссии" in badge_text:
        commission = "без комиссии"

    photos: list[str] = []
    for img in (item.get("images") or item.get("photos") or [])[:5]:
        url = ""
        if isinstance(img, str):
            url = img
        elif isinstance(img, dict):
            url = img.get("636x476") or img.get("url") or img.get("src") or ""
        if url:
            photos.append(url)

    offer_url = item.get("url") or item.get("urlPath") or f"https://www.avito.ru/{item_id}"
    if offer_url.startswith("/"):
        offer_url = f"https://www.avito.ru{offer_url}"

    return Listing(
        listing_id=int(item_id),
        source=Source.AVITO,
        url=offer_url,
        title=title or f"{rooms}-комн. квартира, {total_area} м²",
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
    """Fallback-парсинг из HTML-карточек Авито."""
    listings: List[Listing] = []

    cards = soup.select("[data-marker='item']")

    for card in cards:
        try:
            link_tag = card.select_one("a[itemprop='url']") or card.select_one("a[data-marker='item-title']")
            if not link_tag:
                continue

            href = str(link_tag.get("href", ""))
            id_match = re.search(r"_(\d+)$", href)
            if not id_match:
                continue
            listing_id = int(id_match.group(1))

            title = link_tag.get_text(strip=True) or ""

            price_el = card.select_one("[itemprop='price']") or card.select_one("[data-marker='item-price']")
            price = 0
            if price_el:
                price_attr = price_el.get("content", "")
                if price_attr:
                    price = int(re.sub(r"[^\d]", "", str(price_attr)) or 0)
                else:
                    price = int(re.sub(r"[^\d]", "", price_el.get_text()) or 0)

            address_el = card.select_one("[data-marker='item-address']")
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

            url = href if href.startswith("http") else f"https://www.avito.ru{href}"

            listings.append(Listing(
                listing_id=listing_id,
                source=Source.AVITO,
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
            logger.debug("Ошибка парсинга карточки Авито: %s", exc)
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
    """Выполняет поиск по Авито и возвращает список объявлений (по всем выбранным городам)."""
    all_listings: List[Listing] = []
    seen_ids: set[int] = set()
    slugs = _unique_city_slugs(user_filter)

    async with aiohttp.ClientSession() as session:
        for city_slug in slugs:
            for page in range(1, pages + 1):
                url = build_search_url(user_filter, page=page, city_slug=city_slug)
                logger.info("Запрос Авито (%s): %s", city_slug, url)

                html = await fetch_page(
                    session, url,
                    referer="https://www.avito.ru/",
                    delay_range=(3.0, 8.0),
                )
                if not html:
                    logger.warning("Авито %s стр.%d: пустой ответ", city_slug, page)
                    break

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
                logger.info("Авито %s стр.%d: найдено %d объявлений", city_slug, page, len(page_listings))

                if not page_listings:
                    if page == 1:
                        logger.warning("Авито %s: 0 объявлений на первой странице", city_slug)
                    break

    return all_listings
