import sys
import io
import httpx
from rich.console import Console
from rich.panel import Panel

import config

console = Console()
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

IMAGE_URL = "https://images.unsplash.com/photo-1554118811-1e0d58224f24?w=800"
PROMPT = "Опиши это место. Есть ли розетки? Тихое или шумное? Подходит для работы?"

console.print(Panel(f"[bold]Модель:[/] {config.MODEL_NAME}\n[bold]Фото:[/] {IMAGE_URL}", expand=False))

payload = {
    "model": config.MODEL_NAME,
    "messages": [{
        "role": "user",
        "content": [
            {"type": "image_url", "image_url": {"url": IMAGE_URL}},
            {"type": "text", "text": PROMPT},
        ],
    }],
    "max_tokens": 300,
}

try:
    r = httpx.post(
        f"{config.PROXY_BASE_URL}/chat/completions",
        headers={
            "Authorization": f"Bearer {config.PROXY_API_KEY}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=30,
    )
    data = r.json()

    if r.status_code != 200:
        err = data.get("error", {})
        console.print(f"[red]Ошибка {r.status_code}:[/] {err.get('message', data)}")
        sys.exit(1)

    answer = data["choices"][0]["message"]["content"]
    console.print(Panel(answer, title="[green]Ответ модели", border_style="green"))

except httpx.TimeoutException:
    console.print("[red]Таймаут — прокси не ответил за 30 секунд[/]")
except Exception as e:
    console.print(f"[red]Ошибка:[/] {e}")
