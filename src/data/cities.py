"""Централизованный справочник городов РФ для всех парсеров и UI.

Каждый город содержит:
- id: внутренний идентификатор (стабильный, используется в БД)
- name: русское название
- cian_region: ID региона в ЦИАН (параметр region=)
- slug: транслитерированный slug для Яндекс Недвижимости и Авито
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple


@dataclass(frozen=True)
class City:
    """Город из справочника."""

    id: int
    name: str
    cian_region: int
    slug: str


CITIES: Tuple[City, ...] = (
    City(1, "Москва", 1, "moskva"),
    City(2, "Санкт-Петербург", 2, "sankt-peterburg"),
    City(3, "Новосибирск", 4897, "novosibirsk"),
    City(4, "Екатеринбург", 4743, "ekaterinburg"),
    City(5, "Казань", 4777, "kazan"),
    City(6, "Нижний Новгород", 4749, "nizhniy_novgorod"),
    City(7, "Красноярск", 4827, "krasnoyarsk"),
    City(8, "Челябинск", 4919, "chelyabinsk"),
    City(9, "Самара", 4966, "samara"),
    City(10, "Уфа", 5108, "ufa"),
    City(11, "Ростов-на-Дону", 4959, "rostov-na-donu"),
    City(12, "Краснодар", 4820, "krasnodar"),
    City(13, "Омск", 4854, "omsk"),
    City(14, "Воронеж", 4713, "voronezh"),
    City(15, "Пермь", 4916, "perm"),
    City(16, "Волгоград", 4702, "volgograd"),
    City(17, "Саратов", 4973, "saratov"),
    City(18, "Тюмень", 5106, "tyumen"),
    City(19, "Тольятти", 4966, "tolyatti"),
    City(20, "Махачкала", 4843, "mahachkala"),
    City(21, "Ижевск", 5048, "izhevsk"),
    City(22, "Барнаул", 4676, "barnaul"),
    City(23, "Ульяновск", 5111, "ulyanovsk"),
    City(24, "Иркутск", 4764, "irkutsk"),
    City(25, "Хабаровск", 5118, "habarovsk"),
    City(26, "Ярославль", 5139, "yaroslavl"),
    City(27, "Владивосток", 4696, "vladivostok"),
    City(28, "Томск", 5092, "tomsk"),
    City(29, "Оренбург", 4857, "orenburg"),
    City(30, "Кемерово", 4791, "kemerovo"),
    City(31, "Новокузнецк", 4791, "novokuznetsk"),
    City(32, "Рязань", 4964, "ryazan"),
    City(33, "Набережные Челны", 4783, "naberezhnyye_chelny"),
    City(34, "Астрахань", 4671, "astrahan"),
    City(35, "Пенза", 4908, "penza"),
    City(36, "Липецк", 4838, "lipetsk"),
    City(37, "Тула", 5100, "tula"),
    City(38, "Киров", 4797, "kirov"),
    City(39, "Чебоксары", 5130, "cheboksary"),
    City(40, "Калининград", 4772, "kaliningrad"),
    City(41, "Брянск", 4686, "bryansk"),
    City(42, "Курск", 4835, "kursk"),
    City(43, "Иваново", 4756, "ivanovo"),
    City(44, "Магнитогорск", 4919, "magnitogorsk"),
    City(45, "Улан-Удэ", 4680, "ulan-ude"),
    City(46, "Тверь", 5085, "tver"),
    City(47, "Ставрополь", 5079, "stavropol"),
    City(48, "Нижний Тагил", 4984, "nizhniy_tagil"),
    City(49, "Белгород", 4681, "belgorod"),
    City(50, "Архангельск", 4668, "arhangelsk"),
    City(51, "Владимир", 4697, "vladimir"),
    City(52, "Сочи", 4820, "sochi"),
    City(53, "Курган", 4833, "kurgan"),
    City(54, "Смоленск", 5075, "smolensk"),
    City(55, "Калуга", 4773, "kaluga"),
    City(56, "Чита", 5132, "chita"),
    City(57, "Орёл", 4858, "oryol"),
    City(58, "Волжский", 4702, "volzhskiy"),
    City(59, "Череповец", 4700, "cherepovets"),
    City(60, "Владикавказ", 4978, "vladikavkaz"),
    City(61, "Мурманск", 4847, "murmansk"),
    City(62, "Саранск", 4870, "saransk"),
    City(63, "Сургут", 5120, "surgut"),
    City(64, "Вологда", 4700, "vologda"),
    City(65, "Тамбов", 5082, "tambov"),
    City(66, "Стерлитамак", 5108, "sterlitamak"),
    City(67, "Грозный", 5128, "groznyy"),
    City(68, "Якутск", 5141, "yakutsk"),
    City(69, "Кострома", 4810, "kostroma"),
    City(70, "Комсомольск-на-Амуре", 5118, "komsomolsk-na-amure"),
    City(71, "Петрозаводск", 4913, "petrozavodsk"),
    City(72, "Таганрог", 4959, "taganrog"),
    City(73, "Нижневартовск", 5120, "nizhnevartovsk"),
    City(74, "Йошкар-Ола", 4865, "yoshkar-ola"),
    City(75, "Новороссийск", 4820, "novorossiysk"),
    City(76, "Братск", 4764, "bratsk"),
    City(77, "Дзержинск", 4749, "dzerzhinsk"),
    City(78, "Шахты", 4959, "shahty"),
    City(79, "Нальчик", 4761, "nalchik"),
    City(80, "Орск", 4857, "orsk"),
    City(81, "Сыктывкар", 4803, "syktyvkar"),
    City(82, "Нижнекамск", 4783, "nizhnekamsk"),
    City(83, "Ангарск", 4764, "angarsk"),
    City(84, "Старый Оскол", 4681, "staryy_oskol"),
    City(85, "Великий Новгород", 4848, "velikiy_novgorod"),
    City(86, "Балашиха", 4593, "balashiha"),
    City(87, "Химки", 4593, "himki"),
    City(88, "Подольск", 4593, "podolsk"),
    City(89, "Королёв", 4593, "korolyov"),
    City(90, "Мытищи", 4593, "mytishchi"),
    City(91, "Люберцы", 4593, "lyubertsy"),
    City(92, "Южно-Сахалинск", 5145, "yuzhno-sahalinsk"),
    City(93, "Энгельс", 4973, "engels"),
    City(94, "Благовещенск", 4661, "blagoveshchensk"),
    City(95, "Псков", 4944, "pskov"),
    City(96, "Бийск", 4676, "biysk"),
    City(97, "Прокопьевск", 4791, "prokopyevsk"),
    City(98, "Рыбинск", 5139, "rybinsk"),
    City(99, "Абакан", 5114, "abakan"),
    City(100, "Армавир", 4820, "armavir"),
    City(101, "Норильск", 4827, "norilsk"),
    City(102, "Балаково", 4973, "balakovo"),
    City(103, "Петропавловск-Камчатский", 4775, "petropavlovsk-kamchatskiy"),
    City(104, "Северодвинск", 4668, "severodvinsk"),
    City(105, "Сызрань", 4966, "syzran"),
    City(106, "Златоуст", 4919, "zlatoust"),
    City(107, "Каменск-Уральский", 4984, "kamensk-uralskiy"),
    City(108, "Миасс", 4919, "miass"),
    City(109, "Копейск", 4919, "kopeysk"),
    City(110, "Альметьевск", 4783, "almetevsk"),
    City(111, "Хасавюрт", 4843, "hasavyurt"),
    City(112, "Новочеркасск", 4959, "novocherkassk"),
    City(113, "Первоуральск", 4984, "pervouralsk"),
    City(114, "Кисловодск", 5079, "kislovodsk"),
    City(115, "Пятигорск", 5079, "pyatigorsk"),
    City(116, "Невинномысск", 5079, "nevinnomyssk"),
    City(117, "Серпухов", 4593, "serpuhov"),
    City(118, "Одинцово", 4593, "odintsovo"),
    City(119, "Домодедово", 4593, "domodedovo"),
    City(120, "Красногорск", 4593, "krasnogorsk"),
    City(121, "Щёлково", 4593, "shchyolkovo"),
    City(122, "Дербент", 4843, "derbent"),
    City(123, "Батайск", 4959, "bataysk"),
    City(124, "Назрань", 4755, "nazran"),
    City(125, "Каспийск", 4843, "kaspiysk"),
    City(126, "Ессентуки", 5079, "essentuki"),
    City(127, "Елец", 4838, "elets"),
    City(128, "Новомосковск", 5100, "novomoskovsk"),
    City(129, "Обнинск", 4773, "obninsk"),
    City(130, "Нефтекамск", 5108, "neftekamsk"),
    City(131, "Димитровград", 5111, "dimitrovgrad"),
    City(132, "Кызыл", 5096, "kyzyl"),
    City(133, "Октябрьский", 5108, "oktyabrskiy"),
    City(134, "Новый Уренгой", 5142, "novyy_urengoy"),
    City(135, "Ноябрьск", 5142, "noyabrsk"),
    City(136, "Ачинск", 4827, "achinsk"),
    City(137, "Елабуга", 4783, "elabuga"),
    City(138, "Арзамас", 4749, "arzamas"),
    City(139, "Ковров", 4697, "kovrov"),
    City(140, "Северск", 5092, "seversk"),
    City(141, "Новошахтинск", 4959, "novoshahtinsk"),
    City(142, "Муром", 4697, "murom"),
    City(143, "Жуковский", 4593, "zhukovskiy"),
    City(144, "Евпатория", 4891, "evpatoriya"),
    City(145, "Раменское", 4593, "ramenskoye"),
    City(146, "Долгопрудный", 4593, "dolgoprudnyy"),
    City(147, "Пушкино", 4593, "pushkino"),
    City(148, "Реутов", 4593, "reutov"),
    City(149, "Артём", 4696, "artyom"),
    City(150, "Бердск", 4897, "berdsk"),
    City(151, "Зеленодольск", 4783, "zelenodolsk"),
    City(152, "Черкесск", 4778, "cherkessk"),
    City(153, "Майкоп", 4660, "maykop"),
    City(154, "Тобольск", 5106, "tobolsk"),
    City(155, "Ленинск-Кузнецкий", 4791, "leninsk-kuznetskiy"),
    City(156, "Междуреченск", 4791, "mezhdurechensk"),
    City(157, "Берёзовский", 4984, "beryozovskiy"),
    City(158, "Воткинск", 5048, "votkinsk"),
    City(159, "Минеральные Воды", 5079, "mineralnyye_vody"),
    City(160, "Лобня", 4593, "lobnya"),
    City(161, "Ухта", 4803, "uhta"),
    City(162, "Кинешма", 4756, "kineshma"),
    City(163, "Геленджик", 4820, "gelendzhik"),
    City(164, "Анапа", 4820, "anapa"),
    City(165, "Выборг", 4834, "vyborg"),
    City(166, "Гатчина", 4834, "gatchina"),
    City(167, "Всеволожск", 4834, "vsevolozhsk"),
    City(168, "Магас", 4755, "magas"),
    City(169, "Элиста", 4767, "elista"),
    City(170, "Биробиджан", 5151, "birobidzhan"),
    City(171, "Московская область", 4593, "moskovskaya_oblast"),
    City(172, "Ленинградская область", 4834, "leningradskaya_oblast"),
)

_CITY_BY_ID: Dict[int, City] = {c.id: c for c in CITIES}

# Города с населением > 1 млн (id 1–16 в текущем справочнике)
MILLIONER_CITY_IDS: Tuple[int, ...] = (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16)


def get_millioner_cities() -> List[City]:
    """Возвращает города-миллионники для быстрого выбора."""
    return [c for c in CITIES if c.id in MILLIONER_CITY_IDS]


_CITY_NAMES_LOWER: List[tuple[str, City]] = [
    (c.name.lower(), c) for c in CITIES
]


def get_city_by_id(city_id: int) -> Optional[City]:
    """Возвращает город по внутреннему ID или None."""
    return _CITY_BY_ID.get(city_id)


def get_city_name(city_id: int) -> str:
    """Возвращает название города по ID. Для неизвестных — '—'."""
    city = _CITY_BY_ID.get(city_id)
    return city.name if city else "—"


def get_cities_by_ids(ids: Iterable[int]) -> List[City]:
    """Возвращает список городов по списку ID. Неизвестные ID пропускаются."""
    return [c for i in ids if (c := _CITY_BY_ID.get(i)) is not None]


def get_cities_display(ids: List[int]) -> str:
    """Формирует строку для отображения списка городов (напр. «Москва, Московская область»)."""
    names = [get_city_name(i) for i in ids if get_city_by_id(i)]
    return ", ".join(names) if names else "—"


def search_cities(query: str, limit: int = 8) -> List[City]:
    """Ищет города по подстроке названия (case-insensitive).

    Сначала показывает города, начинающиеся на запрос, затем содержащие его.
    """
    if not query or not query.strip():
        return []

    q = query.strip().lower()

    starts_with: List[City] = []
    contains: List[City] = []

    for name_lower, city in _CITY_NAMES_LOWER:
        if name_lower.startswith(q):
            starts_with.append(city)
        elif q in name_lower:
            contains.append(city)

    result = starts_with + contains
    return result[:limit]
