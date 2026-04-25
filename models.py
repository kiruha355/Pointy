from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    query: str
    location: str = "Москва"
    lat: float = 55.7558
    lon: float = 37.6173
    radius_km: float = Field(default=1.0, gt=0)


class Place(BaseModel):
    name: str
    address: str
    lat: float
    lon: float
    rating: float | None = None
    hours: str | None = None
    has_outlets: bool | None = None
    noise_level: str | None = None
    description: str | None = None
    rubrics: list[str] = Field(default_factory=list)
    maps_url: str | None = None
    phone: str | None = None
    website: str | None = None
    price_level: str | None = None
    photos_count: int = 0
    reviews_count: int = 0
    is_verified: bool = False
    has_wifi: bool | None = None
    good_for_work: bool | None = None
    is_open_now: bool | None = None
    recent_reviews_count: int = 0


class ScoredPlace(BaseModel):
    place: Place
    score: float = Field(ge=0.0, le=10.0)
    reason: str
