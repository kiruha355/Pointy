from rich.console import Console
from rich.table import Table

from map_client import get_map_client

console = Console()

client = get_map_client()
places = client.search_places(query="кафе", lat=55.751244, lon=37.618423, radius=1000)

console.print(f"\n[bold cyan]Найдено мест:[/bold cyan] {len(places)}\n")

table = Table(show_header=True, header_style="bold magenta")
table.add_column("Название", style="bold")
table.add_column("Адрес")
table.add_column("Рейтинг", justify="center")
table.add_column("Категории")

for place in places[:3]:
    rating = str(place["rating"]) if place["rating"] is not None else "—"
    rubrics = ", ".join(place["rubrics"][:2]) if place["rubrics"] else "—"
    table.add_row(place["name"], place["address"], rating, rubrics)

console.print(table)
