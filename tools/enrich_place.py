import json
from pathlib import Path

import httpx

from config import MAPS_API_KEY

_CACHE_FILE = Path(__file__).parent.parent / "data" / "cache_enrich.json"

_OUTLET_KW = {"розетк", "зарядк", "outlet"}
_WIFI_KW   = {"wifi", "вайфай", "wi-fi", "интернет"}
_QUIET_KW  = {"тихо", "спокойно", "тихое"}
_LOUD_KW   = {"шумно", "громко", "шум"}
_WORK_KW   = {"работал", "ноутбук", "работать", "поработать"}


def _enrich_place(place_id: str) -> dict:
    cached = _load_cache(place_id)
    if cached is not None:
        return cached

    result: dict = {}
    try:
        r = httpx.get(
            "https://catalog.api.2gis.com/3.0/items/byid",
            params={
                "id": place_id,
                "key": MAPS_API_KEY,
                "locale": "ru_RU",
                "fields": "items.reviews,items.photos,items.price_comment,items.contact_groups",
            },
            timeout=8,
        )
        r.raise_for_status()
        item = r.json().get("result", {}).get("items", [{}])[0]

        for group in item.get("contact_groups", []):
            for contact in group.get("contacts", []):
                ctype = contact.get("type", "")
                value = contact.get("value", "")
                if ctype == "phone" and not result.get("phone"):
                    result["phone"] = value
                elif ctype in ("website", "url") and not result.get("website"):
                    result["website"] = value

        result["price_level"] = item.get("price_comment")
        photos = item.get("photos", {})
        result["photos_count"] = photos.get("count", 0) if isinstance(photos, dict) else 0
        reviews = item.get("reviews", {})
        result["reviews_count"] = reviews.get("general_review_count", 0)

    except Exception:
        pass

    _save_cache(place_id, result)
    return result


def _scan_text_signals(texts: list[str]) -> dict:
    combined = " ".join(t.lower() for t in texts if t)
    result: dict = {}
    if any(kw in combined for kw in _OUTLET_KW):
        result["has_outlets"] = True
    if any(kw in combined for kw in _WIFI_KW):
        result["has_wifi"] = True
    if any(kw in combined for kw in _WORK_KW):
        result["good_for_work"] = True
    if any(kw in combined for kw in _QUIET_KW):
        result["noise_level"] = "тихо"
    elif any(kw in combined for kw in _LOUD_KW):
        result["noise_level"] = "шумно"
    return result


def _load_cache(key: str) -> dict | None:
    if not _CACHE_FILE.exists():
        return None
    try:
        data = json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
        return data.get(key)
    except Exception:
        return None


def _save_cache(key: str, value: dict) -> None:
    try:
        data: dict = {}
        if _CACHE_FILE.exists():
            data = json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
        data[key] = value
        _CACHE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass
