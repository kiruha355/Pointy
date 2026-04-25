from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from models import SearchRequest
from tools.search_places import search_places
from tools.score_places import score_places

console = Console()

request = SearchRequest(
    query="тихое кафе для работы с ноутбуком",
    location="Москва",
    lat=55.7558,
    lon=37.6173,
    radius_km=1.0,
)

console.rule("[bold cyan]Шаг 1 — поиск мест (2GIS)")
places = search_places(request)
console.print(f"Найдено: [bold]{len(places)}[/bold] мест\n")

console.rule("[bold cyan]Шаг 2 — скоринг")
scored = score_places(places, user_query=request.query)

table = Table(show_header=True, header_style="bold magenta", show_lines=True)
table.add_column("#", width=3, justify="center")
table.add_column("Место", min_width=20)
table.add_column("Адрес", min_width=20)
table.add_column("Балл", justify="center", width=6)
table.add_column("Обоснование", min_width=30)

for i, sp in enumerate(scored[:3], 1):
    p = sp.place
    table.add_row(
        str(i),
        p.name,
        p.address,
        f"[bold green]{sp.score}[/bold green]",
        sp.reason,
    )

console.print(table)
