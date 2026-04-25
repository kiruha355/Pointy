import json
import os
from datetime import datetime
from pathlib import Path

from map_client import get_map_client
from models import Place, SearchRequest
from tools.enrich_place import _enrich_place, _scan_text_signals  # noqa: E402

_CACHE_FILE = Path(__file__).parent.parent / "data" / "cache_search.json"
_RESULTS_DIR = Path(__file__).parent.parent / "data" / "results"


def search_places(request: SearchRequest) -> list[Place]:
    places = _search_with_fallback(request)
    return places


def _search_with_fallback(request: SearchRequest) -> list[Place]:
    places = _search_raw(request)
    if places:
        return places

    # Единственное расширение — до 2 км, больше не пробуем
    expanded_km = min(request.radius_km * 2, 2.0)
    if expanded_km > request.radius_km:
        expanded = request.model_copy(update={"radius_km": expanded_km})
        places = _search_raw(expanded)
        if places:
            print(f"Fallback: расширен радиус до {expanded_km} км")

    return places


def _search_raw(request: SearchRequest) -> list[Place]:
    cache_key = f"{request.query}|{request.lat}|{request.lon}|{request.radius_km}"
    cached = _load_cache(cache_key)
    if cached is not None:
        return [Place(**p) for p in cached]

    client = get_map_client()
    radius_m = int(request.radius_km * 1000)
    raw_items = client.search_places(request.query, request.lat, request.lon, radius_m)

    places: list[Place] = []
    for item in raw_items:
        if item.get("lat") is None or item.get("lon") is None:
            continue

        rating = item.get("rating")
        if isinstance(rating, dict):
            rating = rating.get("rating")

        place_id = item.get("id", "")

        enriched: dict = {}
        if place_id:
            enriched = _enrich_place(place_id)

        text_signals = _scan_text_signals([
            item.get("name", ""),
            item.get("description") or "",
        ])

        places.append(Place(
            name=item.get("name", ""),
            address=item.get("address", ""),
            lat=item["lat"],
            lon=item["lon"],
            rating=float(rating) if rating is not None else None,
            hours=item.get("hours"),
            description=item.get("description"),
            rubrics=item.get("rubrics", []),
            maps_url=f"https://2gis.ru/moscow/search/{item.get('name', '')}",
            phone=enriched.get("phone"),
            website=enriched.get("website"),
            price_level=enriched.get("price_level"),
            photos_count=enriched.get("photos_count", 0),
            reviews_count=enriched.get("reviews_count", 0),
            recent_reviews_count=enriched.get("recent_reviews_count", 0),
            has_outlets=text_signals.get("has_outlets"),
            has_wifi=text_signals.get("has_wifi"),
            good_for_work=text_signals.get("good_for_work"),
            noise_level=text_signals.get("noise_level"),
        ))
        if len(places) >= 10:
            break

    _save_cache(cache_key, [p.model_dump() for p in places])
    if places:
        _save_search_results(request.query, places)
    return places


def _save_search_results(query: str, places: list[Place]) -> None:
    try:
        _RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = _RESULTS_DIR / f"search_{timestamp}.json"
        data = {
            "query": query,
            "timestamp": datetime.now().isoformat(),
            "source": "2GIS Places API",
            "source_url": "https://catalog.api.2gis.com/3.0/items",
            "results_count": len(places),
            "places": [p.model_dump() for p in places],
        }
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _load_cache(key: str) -> list[dict] | None:
    if not _CACHE_FILE.exists():
        return None
    try:
        data = json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
        return data.get(key)
    except Exception:
        return None


def _save_cache(key: str, value: list[dict]) -> None:
    try:
        data: dict = {}
        if _CACHE_FILE.exists():
            data = json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
        data[key] = value
        _CACHE_FILE.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception:
        pass
