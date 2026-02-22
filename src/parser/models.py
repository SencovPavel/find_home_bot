"""Модели данных для объявлений и пользовательских фильтров."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class Source(str, Enum):
    """Площадка-источник объявления."""

    CIAN = "cian"
    AVITO = "avito"
    YANDEX = "yandex"

    @classmethod
    def label(cls, value: str) -> str:
        """Человекочитаемое название площадки."""
        labels: Dict[str, str] = {
            cls.CIAN.value: "ЦИАН",
            cls.AVITO.value: "Авито",
            cls.YANDEX.value: "Яндекс Недвижимость",
        }
        return labels.get(value, value)


class RenovationType(str, Enum):
    """Тип ремонта квартиры."""

    COSMETIC = "cosmetic"
    EURO = "euro"
    DESIGNER = "designer"
    NO_RENOVATION = "no_renovation"

    @classmethod
    def label(cls, value: str) -> str:
        """Человекочитаемое название типа ремонта."""
        labels: Dict[str, str] = {
            cls.COSMETIC.value: "Косметический",
            cls.EURO.value: "Евроремонт",
            cls.DESIGNER.value: "Дизайнерский",
            cls.NO_RENOVATION.value: "Без ремонта",
        }
        return labels.get(value, value)


class MetroTransport(str, Enum):
    """Способ добраться до метро."""

    WALK = "walk"
    TRANSPORT = "transport"

    @classmethod
    def label(cls, value: str) -> str:
        labels: Dict[str, str] = {
            cls.WALK.value: "пешком",
            cls.TRANSPORT.value: "транспортом",
        }
        return labels.get(value, value)


@dataclass
class Listing:
    """Объявление об аренде квартиры."""

    listing_id: int
    source: Source
    url: str
    title: str
    price: int
    address: str
    metro_station: str
    metro_distance_min: int
    metro_transport: MetroTransport
    total_area: float
    kitchen_area: float
    rooms: int
    floor: int
    total_floors: int
    renovation: str
    description: str
    commission: str = ""
    photos: List[str] = field(default_factory=list)


@dataclass
class UserFilter:
    """Фильтры пользователя для поиска квартиры."""

    user_id: int
    cities: List[int] = field(default_factory=lambda: [1])  # список ID городов/регионов
    district: str = ""
    metro: str = ""
    price_min: int = 0
    price_max: int = 0
    area_min: float = 0
    kitchen_area_min: float = 0
    renovation_types: List[str] = field(default_factory=list)
    rooms: List[int] = field(default_factory=list)
    pets_allowed: bool = True
    commission_max_percent: int = 100  # 0 = только без комиссии, 100 = не важно
    tolerance_percent: int = 0
    initial_listings_count: int = 0  # 0 = отключено, 1-30 = сколько показать сразу при старте
    is_active: bool = False
    empty_notified_at: Optional[float] = None  # unix timestamp, сбрасывается при изменении фильтров

    def matches(self, listing: Listing) -> bool:
        """Проверяет, подходит ли объявление под фильтры пользователя."""
        if self.price_min and listing.price < self.price_min:
            return False
        if self.price_max and listing.price > self.price_max:
            return False
        if self.area_min and listing.total_area < self.area_min:
            return False
        if self.kitchen_area_min and listing.kitchen_area < self.kitchen_area_min:
            return False
        if self.rooms and listing.rooms not in self.rooms:
            return False
        if self.renovation_types and listing.renovation not in self.renovation_types:
            return False
        if self.pets_allowed and _listing_has_pet_ban(listing):
            return False
        if self.commission_max_percent < 100:
            parsed = _parse_commission_percent(listing.commission)
            if parsed is None:
                return False
            if parsed > self.commission_max_percent:
                return False
        return True

    def matches_approx(self, listing: Listing) -> Optional[List[str]]:
        """Проверяет, подходит ли объявление с учётом допуска tolerance_percent.

        Возвращает список отклонений от критериев, если объявление «почти подходит».
        Возвращает None, если объявление не подходит даже приблизительно.
        Строгие критерии (комнаты, ремонт, животные, комиссия) проверяются без допуска.
        """
        if self.tolerance_percent <= 0:
            return None

        if self.rooms and listing.rooms not in self.rooms:
            return None
        if self.renovation_types and listing.renovation not in self.renovation_types:
            return None
        if self.pets_allowed and _listing_has_pet_ban(listing):
            return None
        if self.commission_max_percent < 100:
            parsed = _parse_commission_percent(listing.commission)
            if parsed is None or parsed > self.commission_max_percent:
                return None

        factor = self.tolerance_percent / 100
        deviations: List[str] = []

        if self.price_min and listing.price < self.price_min:
            under = (self.price_min - listing.price) / self.price_min
            if under > factor:
                return None
            deviations.append(f"Цена ниже на {under:.0%}")

        if self.price_max and listing.price > self.price_max:
            over = (listing.price - self.price_max) / self.price_max
            if over > factor:
                return None
            deviations.append(f"Цена выше на {over:.0%}")

        if self.area_min and listing.total_area < self.area_min:
            under = (self.area_min - listing.total_area) / self.area_min
            if under > factor:
                return None
            deviations.append(f"Площадь меньше на {under:.0%}")

        if self.kitchen_area_min and listing.kitchen_area < self.kitchen_area_min:
            under = (self.kitchen_area_min - listing.kitchen_area) / self.kitchen_area_min
            if under > factor:
                return None
            deviations.append(f"Кухня меньше на {under:.0%}")

        return deviations if deviations else None


_PET_BAN_PHRASES = (
    "без животных",
    "без домашних животных",
    "животные запрещены",
    "не с животными",
    "без питомцев",
    "питомцы запрещены",
    "животных не держать",
    "без кошек",
    "без собак",
    "кошек и собак не держать",
    "проживание с животными запрещено",
    "проживание с животными не допускается",
    "животных не заводить",
)

_NO_COMMISSION_MARKERS = (
    "без комиссии",
    "комиссия 0",
)


def _parse_commission_percent(commission: str) -> int | None:
    """Извлекает процент комиссии из строки. 0 = без комиссии, None = нераспознанный формат."""
    if not commission:
        return 0
    lower = commission.lower().strip()
    if lower in ("0", "0%"):
        return 0
    if any(marker in lower for marker in _NO_COMMISSION_MARKERS):
        return 0
    match = re.search(r"(\d+(?:[.,]\d+)?)\s*%?", lower)
    if match:
        try:
            val = float(match.group(1).replace(",", "."))
            return min(100, max(0, int(round(val))))
        except ValueError:
            pass
    return None


def _has_pet_ban(text: str) -> bool:
    """Эвристика: проверяет наличие явного запрета на животных в тексте."""
    lower = (text or "").lower()
    return any(phrase in lower for phrase in _PET_BAN_PHRASES)


def _listing_has_pet_ban(listing: Listing) -> bool:
    """Проверяет запрет на животных в title и description."""
    text = f"{listing.title or ''} {listing.description or ''}"
    return _has_pet_ban(text)


def _has_commission(commission: str) -> bool:
    """Возвращает True, если в объявлении указана комиссия (не 'без комиссии')."""
    if not commission:
        return False
    lower = commission.lower().strip()
    if lower == "0%" or lower == "0":
        return False
    if any(marker in lower for marker in _NO_COMMISSION_MARKERS):
        return False
    return True
