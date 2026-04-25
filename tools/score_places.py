import asyncio
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path

import httpx
from pydantic import BaseModel, Field

import config
from models import Place, ScoredPlace

_CACHE_FILE = Path(__file__).parent.parent / "data" / "cache_scores.json"

# ── Типы запросов (нужны для detect_query_type который используется в server.py) ──
QUERY_TYPES: dict[str, list[str]] = {
    "work":      ["работать", "работы", "работе", "ноутбук", "коворкинг",
                  "поработать", "учиться", "тихо", "тихое", "тихий",
                  "спокойно", "розетки", "wi-fi", "вайфай"],
    "eat":       ["поесть", "обед", "ужин", "перекусить", "хинкали",
                  "пицца", "суши", "кухня", "покушать", "еда", "поем"],
    "beautiful": ["красивое", "необычное", "атмосферное", "интересное",
                  "уютное", "стильное", "инстаграм", "фото"],
    "fast":      ["быстро", "рядом", "недалеко", "на", "ходу", "перекус"],
}


def detect_query_type(user_query: str) -> str:
    words = set(user_query.lower().split())
    scores = {qtype: len(words & set(kws)) for qtype, kws in QUERY_TYPES.items()}
    best_type, best_score = max(scores.items(), key=lambda x: x[1])
    return best_type if best_score > 0 else "general"


# ── Pydantic модель для ответа LLM ────────────────────────────────────────────

class PlaceScore(BaseModel):
    score: float = Field(ge=0.0, le=10.0)
    reason: str


# ── Публичный sync-интерфейс (вызывается из agent.py) ────────────────────────

def score_places(places: list[Place], user_query: str = "") -> list[ScoredPlace]:
    return asyncio.run(_score_places_async(places, user_query))


# ── Async core ────────────────────────────────────────────────────────────────

async def _score_places_async(
    places: list[Place],
    user_query: str,
    limit: int = 5,
    min_score: float = 4.0,
) -> list[ScoredPlace]:
    tasks = [_score_single_place(p, user_query) for p in places]
    results = await asyncio.gather(*tasks)
    filtered = [r for r in results if r.score >= min_score]
    return sorted(filtered, key=lambda x: x.score, reverse=True)[:limit]


async def _score_single_place(place: Place, user_query: str) -> ScoredPlace:
    cache_key = _cache_key(place, user_query)
    cached = _load_cache(cache_key)
    if cached:
        return ScoredPlace(place=place, score=cached["score"], reason=cached["reason"])

    # Определяем открытость детерминированно — LLM это не знает
    hours_score, is_open_label = _check_hours(place.hours)

    prompt = f"""Пользователь ищет: "{user_query}"

Место: {place.name}
Категории: {', '.join(place.rubrics) if place.rubrics else 'нет данных'}
Описание: {place.description or 'нет описания'}
Рейтинг: {place.rating if place.rating is not None else 'нет данных'}
Часы работы: {place.hours or 'нет данных'}
Сейчас открыто: {is_open_label}
Число отзывов: {place.reviews_count if place.reviews_count else 'нет данных'}

Оцени от 0 до 10 насколько это место подходит под запрос пользователя.
Учитывай: соответствие типа места запросу, рейтинг, открыто ли сейчас, детали из описания и категорий.
Если место закрыто — оценка не выше 4.

Отвечай ТОЛЬКО в JSON без лишнего текста:
{{"score": 7.5, "reason": "одно предложение почему"}}"""

    result = await _call_llm(prompt)

    if result is None:
        # Fallback: детерминированный скоринг
        result = _deterministic_fallback(place, user_query, hours_score)

    # Применяем жёсткий штраф за закрытость поверх LLM оценки
    if hours_score < 0 and result.score > 4.0:
        result = PlaceScore(score=min(result.score, 3.0), reason=result.reason + " (сейчас закрыто)")

    _save_cache(cache_key, {"score": result.score, "reason": result.reason})
    return ScoredPlace(place=place, score=result.score, reason=result.reason)


async def _call_llm(prompt: str) -> PlaceScore | None:
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(
                f"{config.PROXY_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {config.PROXY_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": config.MODEL_NAME,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 80,
                    "temperature": 0.0,
                },
            )
            r.raise_for_status()
            text = r.json()["choices"][0]["message"]["content"] or ""
            match = re.search(r'\{[^{}]*"score"[^{}]*\}', text, re.DOTALL)
            if not match:
                return None
            data = json.loads(match.group())
            return PlaceScore(
                score=float(data["score"]),
                reason=str(data.get("reason", "")),
            )
    except Exception:
        return None


# ── Детерминированный fallback ────────────────────────────────────────────────

def _deterministic_fallback(place: Place, user_query: str, hours_score: float) -> PlaceScore:
    score = 0.0
    parts: list[str] = []
    query_words = set(user_query.lower().split())
    rubrics_lower = {r.lower() for r in place.rubrics}

    if place.rating is not None:
        r = min(place.rating / 5.0 * 4.0, 4.0)
        score += r
        parts.append(f"рейтинг {place.rating}")
    else:
        score += 2.0
        parts.append("рейтинг неизвестен")

    score += hours_score
    if hours_score > 0:
        parts.append("открыто")
    elif hours_score < 0:
        parts.append("закрыто")

    food = {"ресторан", "кафе", "столовая", "бистро", "кофейня", "пекарня"}
    cowork = {"коворкинг", "библиотека", "антикафе"}
    if rubrics_lower & cowork:
        score += 2.0
        parts.append("коворкинг")
    elif rubrics_lower & food:
        score += 1.0
        parts.append("кафе/ресторан")

    name_words = set((place.name or "").lower().split())
    if (name_words | rubrics_lower) & query_words:
        score += 1.0
        parts.append("совпадение с запросом")

    return PlaceScore(
        score=round(max(0.0, min(score, 10.0)), 2),
        reason="[fallback] " + ", ".join(parts),
    )


# ── Утилиты ───────────────────────────────────────────────────────────────────

def _check_hours(hours: str | None) -> tuple[float, str]:
    if hours is None:
        return 0.0, "нет данных"
    now = datetime.now()
    day_ru = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"][now.weekday()]
    for seg in hours.split(","):
        seg = seg.strip()
        if not seg.startswith(day_ru):
            continue
        try:
            times = seg.split(" ", 1)[1]
            o, c = times.split("–")
            oh, om = map(int, o.strip().split(":"))
            ch, cm = map(int, c.strip().split(":"))
            cur = now.hour * 60 + now.minute
            if oh * 60 + om <= cur <= ch * 60 + cm:
                return 2.0, "да"
            return -3.0, "нет"
        except Exception:
            continue
    return 0.0, "нет данных"


def _cache_key(place: Place, query: str) -> str:
    raw = f"{place.name}|{place.address}|{query}"
    return hashlib.md5(raw.encode()).hexdigest()


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
