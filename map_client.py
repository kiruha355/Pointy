"""
Map data provider abstraction.

To switch from 2GIS to another provider (Google Places, Foursquare, etc.):
1. Replace the implementation inside TwoGisClient with calls to the new API.
2. Keep the MapClient interface intact — no other files need to change.
"""

import json
from abc import ABC, abstractmethod
from pathlib import Path

import httpx

from config import MAPS_API_KEY

_GEOCODE_CACHE = Path(__file__).parent / "data" / "cache_geocode.json"


async def geocode_location(query: str) -> tuple[float, float] | None:
    key = query.lower().strip()
    cached = _geocode_load(key)
    if cached:
        return cached["lat"], cached["lon"]

    async with httpx.AsyncClient(timeout=8) as client:
        r = await client.get(
            "https://catalog.api.2gis.com/3.0/items/geocode",
            params={
                "q": f"{query}, Москва",
                "key": MAPS_API_KEY,
                "fields": "items.point",
                "locale": "ru_RU",
            },
        )

    items = r.json().get("result", {}).get("items", [])
    if not items:
        return None

    point = items[0].get("point", {})
    if not point.get("lat"):
        return None

    lat, lon = point["lat"], point["lon"]
    _geocode_save(key, {"lat": lat, "lon": lon})
    return lat, lon


def _geocode_load(key: str) -> dict | None:
    if not _GEOCODE_CACHE.exists():
        return None
    try:
        return json.loads(_GEOCODE_CACHE.read_text(encoding="utf-8")).get(key)
    except Exception:
        return None


def _geocode_save(key: str, value: dict) -> None:
    try:
        data: dict = {}
        if _GEOCODE_CACHE.exists():
            data = json.loads(_GEOCODE_CACHE.read_text(encoding="utf-8"))
        data[key] = value
        _GEOCODE_CACHE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass

_DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
_DAYS_RU = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


class MapClient(ABC):
    @abstractmethod
    def search_places(self, query: str, lat: float, lon: float, radius: int = 2000) -> list[dict]:
        ...

    @abstractmethod
    def get_place_details(self, place_id: str) -> dict:
        ...


class TwoGisClient(MapClient):
    BASE_URL = "https://catalog.api.2gis.com/3.0"
    FIELDS = (
        "items.point,"
        "items.address,"
        "items.rating,"
        "items.schedule,"
        "items.description,"
        "items.rubrics,"
        "items.name_ex"
    )

    def __init__(self) -> None:
        self._key = MAPS_API_KEY

    def search_places(self, query: str, lat: float, lon: float, radius: int = 2000) -> list[dict]:
        response = httpx.get(
            f"{self.BASE_URL}/items",
            params={
                "q": query,
                "point": f"{lon},{lat}",
                "radius": radius,
                "fields": self.FIELDS,
                "key": self._key,
                "page_size": 10,
                "locale": "ru_RU",
            },
            timeout=10,
        )
        response.raise_for_status()
        items = response.json().get("result", {}).get("items", [])
        return [self._parse(item) for item in items if item.get("point")]

    def get_place_details(self, place_id: str) -> dict:
        response = httpx.get(
            f"{self.BASE_URL}/items/byid",
            params={
                "id": place_id,
                "fields": self.FIELDS,
                "key": self._key,
                "locale": "ru_RU",
            },
            timeout=10,
        )
        response.raise_for_status()
        items = response.json().get("result", {}).get("items", [])
        return self._parse(items[0]) if items else {}

    def _parse(self, item: dict) -> dict:
        point = item.get("point", {})
        rubrics = [r["name"] for r in item.get("rubrics", []) if r.get("name")]
        place_id = item.get("id", "")
        return {
            "id": place_id,
            "name": item.get("name", ""),
            "address": item.get("address_name", ""),
            "lat": point.get("lat"),
            "lon": point.get("lon"),
            "rating": item.get("rating"),
            "hours": _parse_hours(item.get("schedule")),
            "description": item.get("description"),
            "rubrics": rubrics,
            "maps_url": f"https://2gis.ru/firm/{place_id}" if place_id else None,
        }


def _parse_hours(schedule: dict | None) -> str | None:
    if not schedule:
        return None
    parts = []
    for day_en, day_ru in zip(_DAYS, _DAYS_RU):
        day_data = schedule.get(day_en)
        if day_data and day_data.get("working_hours"):
            wh = day_data["working_hours"][0]
            parts.append(f"{day_ru} {wh['from']}–{wh['to']}")
    return ", ".join(parts) if parts else None


def get_map_client() -> MapClient:
    # Swap TwoGisClient for any MapClient subclass to change provider.
    return TwoGisClient()
