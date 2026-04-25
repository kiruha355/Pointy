from collections import defaultdict, deque
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from agent import SearchDeps, agent
from models import ScoredPlace
from tools.score_places import detect_query_type

MOSCOW_LAT = 55.7558
MOSCOW_LON = 37.6173
FRONTEND = Path(__file__).parent / "frontend"

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=FRONTEND), name="static")

# Хранилище сессий (in-memory, живёт пока сервер запущен)
sessions: dict = defaultdict(lambda: {
    "history": deque(maxlen=5),
    "last_results": [],
    "messages": [],
})


class ChatRequest(BaseModel):
    query: str
    lat: float | None = None
    lon: float | None = None
    radius_km: float = 1.0


class PlaceOut(BaseModel):
    name: str
    address: str
    lat: float
    lon: float
    score: float
    reason: str
    maps_url: str | None
    is_open: bool


class ChatResponse(BaseModel):
    message: str
    places: list[PlaceOut]


def _extract_scored(result) -> list[ScoredPlace]:
    for msg in result.all_messages():
        for part in getattr(msg, "parts", []):
            if (
                getattr(part, "part_kind", "") == "tool-return"
                and getattr(part, "tool_name", "") == "score_places"
            ):
                content = getattr(part, "content", None)
                if isinstance(content, list) and content and isinstance(content[0], ScoredPlace):
                    return content
    return []


def _to_place_out(sp: ScoredPlace) -> PlaceOut:
    is_open = "сейчас открыто" in sp.reason
    return PlaceOut(
        name=sp.place.name,
        address=sp.place.address,
        lat=sp.place.lat,
        lon=sp.place.lon,
        score=sp.score,
        reason=sp.reason,
        maps_url=sp.place.maps_url,
        is_open=is_open,
    )


def format_session_context(session: dict) -> str:
    history = session["history"]
    if not history:
        return ""
    lines = ["История запросов в этой сессии:"]
    for i, h in enumerate(history, 1):
        lines.append(
            f"{i}. '{h['query']}' — "
            f"найдено {h['result_count']} мест, "
            f"район: {h['location']}, "
            f"тип: {h['query_type']}"
        )
    last = session["last_results"]
    if last:
        names = ", ".join(p["name"] for p in last[:3])
        lines.append(f"Последние найденные места: {names}")
    return "\n".join(lines)


@app.get("/")
async def index():
    return FileResponse(FRONTEND / "index.html")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, request: Request):
    session_id = request.headers.get("X-Session-ID", "default")
    session = sessions[session_id]

    deps = SearchDeps(
        lat=req.lat if req.lat is not None else MOSCOW_LAT,
        lon=req.lon if req.lon is not None else MOSCOW_LON,
        radius_km=req.radius_km,
    )

    # Формируем контекст сессии и добавляем в начало промпта
    session_ctx = format_session_context(session)
    full_query = f"{session_ctx}\n\nЗапрос пользователя: {req.query}" if session_ctx else req.query

    try:
        result = await agent.run(full_query, deps=deps)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    scored = _extract_scored(result)

    # Сохраняем в историю сессии
    session["history"].append({
        "query": req.query,
        "brand": "",
        "query_type": detect_query_type(req.query),
        "result_count": len(scored),
        "location": "Москва",
        "radius_km": req.radius_km,
    })
    session["last_results"] = [
        {"name": sp.place.name, "lat": sp.place.lat, "lon": sp.place.lon}
        for sp in scored
    ]

    return ChatResponse(
        message=result.output,
        places=[_to_place_out(sp) for sp in scored],
    )
