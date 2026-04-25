import sys
import httpx
import litellm
from rich.console import Console
from rich.table import Table

import config

console = Console()
results: list[tuple[str, bool, str]] = []


def run_test(name: str):
    def decorator(fn):
        console.rule(f"[bold cyan]{name}")
        try:
            fn()
            return True
        except Exception as e:
            console.print(f"[red]ОШИБКА:[/red] {e}")
            results.append((name, False, str(e)))
            return False
    return decorator


# ── Тест 1: LLM ──────────────────────────────────────────────────────────────
console.rule("[bold cyan]Тест 1 — LLM")
try:
    response = litellm.completion(
        model=config.MODEL_NAME,
        api_base=config.PROXY_BASE_URL,
        api_key=config.PROXY_API_KEY,
        messages=[{"role": "user", "content": "ответь одним словом: работает"}],
        max_tokens=20,
    )
    answer = response.choices[0].message.content or ""
    console.print(f"[green]OK[/green] — модель ответила: [bold]{answer.strip()}[/bold]")
    results.append(("LLM", True, answer.strip()))
except Exception as e:
    console.print(f"[red]ОШИБКА:[/red] {e}")
    results.append(("LLM", False, str(e)))


# ── Тест 2: Tool calling ─────────────────────────────────────────────────────
console.rule("[bold cyan]Тест 2 — Tool calling")
try:
    tools = [{
        "type": "function",
        "function": {
            "name": "get_number",
            "description": "Returns the number 42",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    }]
    response = litellm.completion(
        model=config.MODEL_NAME,
        api_base=config.PROXY_BASE_URL,
        api_key=config.PROXY_API_KEY,
        messages=[{"role": "user", "content": "вызови инструмент get_number и скажи что получил"}],
        tools=tools,
        tool_choice="auto",
        max_tokens=50,
    )
    msg = response.choices[0].message
    if msg.tool_calls:
        tool_name = msg.tool_calls[0].function.name
        console.print(f"[green]OK[/green] — модель вызвала инструмент: [bold]{tool_name}[/bold]")
        results.append(("Tool calling", True, tool_name))
    else:
        text = (msg.content or "").strip()
        console.print(f"[yellow]ПРЕДУПРЕЖДЕНИЕ[/yellow] — модель не вызвала инструмент, ответила текстом: {text[:80]}")
        results.append(("Tool calling", False, f"tool_calls отсутствует, content={text[:60]}"))
except Exception as e:
    console.print(f"[red]ОШИБКА:[/red] {e}")
    results.append(("Tool calling", False, str(e)))


# ── Тест 3: 2GIS API ─────────────────────────────────────────────────────────
console.rule("[bold cyan]Тест 3 — 2GIS API")
try:
    if not config.MAPS_API_KEY:
        raise ValueError("MAPS_API_KEY не задан в .env")
    r = httpx.get(
        "https://catalog.api.2gis.com/3.0/items",
        params={
            "q": "кафе",
            "point": "37.618423,55.751244",
            "radius": 1000,
            "key": config.MAPS_API_KEY,
            "locale": "ru_RU",
        },
        timeout=10,
    )
    r.raise_for_status()
    items = r.json().get("result", {}).get("items", [])
    console.print(f"[green]OK[/green] — найдено мест: [bold]{len(items)}[/bold]")
    results.append(("2GIS API", True, f"{len(items)} мест"))
except Exception as e:
    console.print(f"[red]ОШИБКА:[/red] {e}")
    results.append(("2GIS API", False, str(e)))


# ── Итог ─────────────────────────────────────────────────────────────────────
console.rule("[bold]Итог")
table = Table(show_header=True, header_style="bold")
table.add_column("Тест", style="cyan")
table.add_column("Статус")
table.add_column("Детали")

for name, ok, detail in results:
    status = "[green]OK[/green]" if ok else "[red]FAIL[/red]"
    table.add_row(name, status, detail[:80])

console.print(table)
all_ok = all(ok for _, ok, _ in results)
sys.exit(0 if all_ok else 1)
