"""Модели данных для объявлений и пользовательских фильтров."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List


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

    cian_id: int
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
    photos: List[str] = field(default_factory=list)


@dataclass
class UserFilter:
    """Фильтры пользователя для поиска квартиры."""

    user_id: int
    city: int = 1  # 1 = Москва, 2 = СПб
    district: str = ""
    metro: str = ""
    price_min: int = 0
    price_max: int = 0
    area_min: float = 0
    kitchen_area_min: float = 0
    renovation_types: List[str] = field(default_factory=list)
    rooms: List[int] = field(default_factory=list)
    pets_allowed: bool = True
    is_active: bool = False

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
        if self.pets_allowed and _has_pet_ban(listing.description):
            return False
        return True


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


def _has_pet_ban(description: str) -> bool:
    """Эвристика: проверяет наличие явного запрета на животных в тексте описания."""
    lower = description.lower()
    return any(phrase in lower for phrase in _PET_BAN_PHRASES)
