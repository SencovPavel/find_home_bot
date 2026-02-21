"""Тесты централизованного справочника городов."""

from __future__ import annotations

from src.data.cities import (
    CITIES,
    City,
    get_city_by_id,
    get_city_name,
    get_millioner_cities,
    search_cities,
)


def test_cities_tuple_is_not_empty() -> None:
    """Справочник содержит города."""
    assert len(CITIES) >= 100


def test_all_cities_have_unique_ids() -> None:
    """Все ID городов уникальны."""
    ids = [c.id for c in CITIES]
    assert len(ids) == len(set(ids))


def test_get_millioner_cities_contains_top_cities() -> None:
    """Города-миллионники включают Москву, СПб, Новосибирск."""
    millioners = get_millioner_cities()
    names = [c.name for c in millioners]
    assert "Москва" in names
    assert "Санкт-Петербург" in names
    assert "Новосибирск" in names
    assert len(millioners) >= 10


def test_moscow_is_id_1() -> None:
    """Москва имеет ID=1."""
    city = get_city_by_id(1)
    assert city is not None
    assert city.name == "Москва"
    assert city.cian_region == 1
    assert city.slug == "moskva"


def test_spb_is_id_2() -> None:
    """Санкт-Петербург имеет ID=2."""
    city = get_city_by_id(2)
    assert city is not None
    assert city.name == "Санкт-Петербург"
    assert city.slug == "sankt-peterburg"


def test_get_city_by_id_returns_none_for_unknown() -> None:
    """Неизвестный ID возвращает None."""
    assert get_city_by_id(99999) is None


def test_get_city_name_known() -> None:
    """Возвращает название известного города."""
    assert get_city_name(1) == "Москва"
    assert get_city_name(3) == "Новосибирск"


def test_get_city_name_unknown_returns_dash() -> None:
    """Для неизвестного ID возвращает '—'."""
    assert get_city_name(99999) == "—"


def test_search_cities_by_prefix() -> None:
    """Поиск по началу названия находит города."""
    results = search_cities("Моск")
    assert any(c.name == "Москва" for c in results)


def test_search_cities_by_substring() -> None:
    """Поиск по подстроке внутри названия находит города."""
    results = search_cities("Петербург")
    assert any(c.name == "Санкт-Петербург" for c in results)


def test_search_cities_case_insensitive() -> None:
    """Поиск регистронезависимый."""
    results = search_cities("москва")
    assert any(c.name == "Москва" for c in results)

    results_upper = search_cities("КАЗАНЬ")
    assert any(c.name == "Казань" for c in results_upper)


def test_search_cities_prefix_priority() -> None:
    """Города, начинающиеся на запрос, идут первыми."""
    results = search_cities("Ново")
    names = [c.name for c in results]
    assert len(names) > 0
    assert all(n.lower().startswith("ново") for n in names[:3])


def test_search_cities_respects_limit() -> None:
    """Результат ограничен параметром limit."""
    results = search_cities("а", limit=3)
    assert len(results) <= 3


def test_search_cities_empty_query_returns_empty() -> None:
    """Пустой запрос возвращает пустой список."""
    assert search_cities("") == []
    assert search_cities("   ") == []


def test_search_cities_no_match_returns_empty() -> None:
    """Несуществующий город возвращает пустой список."""
    assert search_cities("Xylofrgtq") == []


def test_all_cities_have_valid_slugs() -> None:
    """Все slugs непустые и содержат только допустимые символы."""
    import re

    pattern = re.compile(r"^[a-z0-9_-]+$")
    for city in CITIES:
        assert city.slug, f"Пустой slug у {city.name}"
        assert pattern.match(city.slug), f"Недопустимый slug '{city.slug}' у {city.name}"


def test_all_cities_have_positive_cian_region() -> None:
    """Все ЦИАН-регионы положительные."""
    for city in CITIES:
        assert city.cian_region > 0, f"cian_region <= 0 у {city.name}"


def test_city_dataclass_is_frozen() -> None:
    """City — immutable dataclass."""
    city = City(1, "Тест", 100, "test")
    try:
        city.name = "Другой"  # type: ignore[misc]
        assert False, "FrozenInstanceError не был выброшен"
    except AttributeError:
        pass
