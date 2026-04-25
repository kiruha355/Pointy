from pathlib import Path

import folium

from models import ScoredPlace

OUTPUTS_DIR = Path(__file__).parent / "outputs"


def generate_map(places: list[ScoredPlace], output_path: str = "outputs/map.html") -> Path:
    if not places:
        raise ValueError("No places to render.")

    center_lat = sum(p.place.lat for p in places) / len(places)
    center_lon = sum(p.place.lon for p in places) / len(places)

    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=15,
        tiles="OpenStreetMap",
    )

    for sp in places:
        p = sp.place
        color = _score_to_color(sp.score)

        popup_html = f"""
        <div style="font-family: sans-serif; min-width: 200px;">
            <b style="font-size: 14px;">{p.name}</b><br>
            <span style="color: #666;">{p.address}</span><br><br>
            <b>Оценка: {sp.score:.1f}/10</b><br>
            <span style="color: #444;">{sp.reason}</span><br><br>
            {"<span style='color:green;'>✓ Сейчас открыто</span>" if p.hours and "открыто" in sp.reason else ""}
            {"<span style='color:red;'>✗ Сейчас закрыто</span>" if p.hours and "закрыто" in sp.reason else ""}
            <br>
            {f'<a href="{p.maps_url}" target="_blank" style="color:#1a73e8;">Открыть в 2GIS →</a>' if p.maps_url else ""}
        </div>
        """.strip()

        folium.Marker(
            location=[p.lat, p.lon],
            popup=folium.Popup(popup_html, max_width=280),
            tooltip=f"{p.name} · {sp.score:.1f}/10",
            icon=folium.Icon(color=color, icon="coffee", prefix="fa"),
        ).add_to(m)

    OUTPUTS_DIR.mkdir(exist_ok=True)
    path = Path(output_path) if not Path(output_path).is_absolute() else Path(output_path)
    if not path.is_absolute():
        path = Path(__file__).parent / output_path
    path.parent.mkdir(parents=True, exist_ok=True)
    m.save(str(path))
    return path


def _score_to_color(score: float) -> str:
    if score >= 7.0:
        return "green"
    if score >= 5.0:
        return "orange"
    return "red"
