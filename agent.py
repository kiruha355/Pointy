from dataclasses import dataclass

import litellm
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider

import config
from map_client import geocode_location
from models import Place, SearchRequest, ScoredPlace
from tools.search_places import search_places as _search_places
from tools.score_places import _score_places_async

litellm.api_base = config.PROXY_BASE_URL
litellm.api_key = config.PROXY_API_KEY

_model = OpenAIModel(
    model_name=config.MODEL_NAME,
    provider=OpenAIProvider(
        base_url=config.PROXY_BASE_URL,
        api_key=config.PROXY_API_KEY,
    ),
)


@dataclass
class SearchDeps:
    lat: float
    lon: float
    radius_km: float


_SYSTEM_PROMPT = """
Ты помощник который находит места в городе под запрос пользователя.

ПАМЯТЬ СЕССИИ:
В начале каждого запроса может прийти история последних 5 запросов пользователя.
Используй её для понимания контекста.

Правила:
- "покажи ещё" / "ещё места" → повтори последний запрос из history
- "вернись к [X]" → найди запрос про X в history и повтори его
- если запрос явно новый → начинай новый поиск

УТОЧНЯЮЩИЙ ВОПРОС:
Сразу ищи если понятен тип места + контекст.
Уточняй ТОЛЬКО если запрос совсем без деталей ("найди место", "что посоветуешь").
Один вопрос. После ответа — сразу ищи.

ГЕОГРАФИЧЕСКИЙ ОХВАТ:
- "вся Москва" / "везде" → radius_km=15
- конкретный район/метро → вызови extract_location, radius_km=2.0
- "рядом" или ничего → radius_km=1.0
- "[метка]" в запросе → используй координаты метки, НЕ вызывай extract_location

КОЛИЧЕСТВО МЕСТ:
- N > 20 → предупреди "Показываю максимум 20 мест"
- Найдено меньше N → "Нашлось X из N мест в этом радиусе"
- По умолчанию → топ-5

ПОРЯДОК ВЫЗОВА ИНСТРУМЕНТОВ:

ШАГ 1 — если в запросе есть район/улица/метро/место:
  ВЫЗОВИ extract_location, передав ТОЛЬКО название места.
  Примеры:
    "тихое кафе на Арбате"           → extract_location("Арбат")
    "поесть у Третьяковки"           → extract_location("Третьяковская галерея")
    "коворкинг у Патриарших"         → extract_location("Патриаршие пруды")
    "кафе в центре"                  → extract_location("центр Москвы")
  Если в запросе написано "[метка]" → ПРОПУСТИ этот шаг.

ШАГ 2 — ВЫЗОВИ search_places.
  - query: строка запроса (без названия места)
  - Если был extract_location → передай его lat/lon и radius_km=2.0
  - Если "вся Москва" → НЕ указывай lat/lon, radius_km=15
  - Если "[метка]" → НЕ указывай lat/lon (возьмутся из контекста)
  - Иначе → НЕ указывай lat/lon

ШАГ 3 — ВЫЗОВИ score_places.
  places: результат шага 2, user_query: дословная фраза пользователя.

ШАГ 4 — Сформируй ответ:
  - Живой текст, как советуешь другу
  - Упоминай район: "Вот что нашла рядом с Арбатом", "у Патриарших прудов"
  - НЕ говори "в Москве" если есть конкретный район или метка
  - Если радиус расширялся: "В радиусе 1 км не нашла — показываю ближайшее в 2 км"
  - Если место закрыто — обязательно упомяни
  - Если место явно не подходит — не упоминай

ВАЖНО: никогда не используй "скорее всего", "предполагаю", "вероятно есть".
Опирайся только на данные от инструментов.
Отвечай на русском языке.
""".strip()

agent = Agent(
    model=_model,
    system_prompt=_SYSTEM_PROMPT,
    deps_type=SearchDeps,
)


@agent.tool
async def extract_location(_ctx: RunContext[SearchDeps], location_query: str) -> dict:
    """
    Геокодирует название места/района/метро в координаты через 2GIS.
    Вызывай ПЕРВЫМ если в запросе пользователя есть упоминание места.
    Передавай ТОЛЬКО название места — без описания того что ищут.

    Возвращает lat, lon, location_name, found.
    """
    result = await geocode_location(location_query)

    if result:
        lat, lon = result
        print(f"Геокодер: '{location_query}' → lat={lat:.4f}, lon={lon:.4f}")
        return {"lat": lat, "lon": lon, "location_name": location_query, "found": True}

    print(f"Геокодер: '{location_query}' → не найдено, используем центр Москвы")
    return {"lat": 55.7558, "lon": 37.6173, "location_name": "центр Москвы", "found": False}


@agent.tool
async def search_places(ctx: RunContext[SearchDeps], request: SearchRequest) -> list[Place]:
    """
    Search for places via the map API.
    If extract_location was called — pass its lat/lon explicitly.
    If user set a pin ([метка]) — omit lat/lon, they come from context.
    radius_km: 2.0 for districts, 15 for whole Moscow, 1.0 default.
    """
    user_pinned = (ctx.deps.lat != 55.7558 or ctx.deps.lon != 37.6173)
    if user_pinned:
        request.lat = ctx.deps.lat
        request.lon = ctx.deps.lon
        request.radius_km = ctx.deps.radius_km
    else:
        if request.lat == 55.7558 and request.lon == 37.6173:
            request.lat = ctx.deps.lat
            request.lon = ctx.deps.lon
        if request.radius_km == 1.0:
            request.radius_km = ctx.deps.radius_km

    source = "метка" if user_pinned else ("геокодер/охват" if (request.lat, request.lon) != (55.7558, 37.6173) or request.radius_km > 1.0 else "центр Москвы")
    print(f"Поиск: lat={request.lat:.4f}, lon={request.lon:.4f}, radius={request.radius_km}км, источник={source}")

    return _search_places(request)


@agent.tool
async def score_places(
    ctx: RunContext[SearchDeps],
    places: list[Place],
    user_query: str,
) -> list[ScoredPlace]:
    """
    Оценивает и ранжирует места по соответствию запросу пользователя.

    ВАЖНО: параметр user_query — это дословная строка запроса
    пользователя на русском языке. Всегда передавай его явно.
    Пример: user_query="тихое кафе для работы с ноутбуком"
    """
    return await _score_places_async(places, user_query)
