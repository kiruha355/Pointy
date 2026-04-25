Track: A + C

AI-агент на Python, который принимает запрос пользователя на естественном языке, ищет подходящие места в городе через 2GIS API, оценивает их по критериям тишины, часов работы и соответствия запросу, выдаёт текстовую рекомендацию с ссылками и отображает результаты на интерактивной карте.

## Стек

- Python 3.11+
- PydanticAI — агентный фреймворк
- LiteLLM — подключение LLM через прокси
- Pydantic — модели данных
- FastAPI + Uvicorn — веб-сервер
- 2GIS API — источник данных о местах
- Leaflet.js — интерактивная карта в браузере
- python-dotenv — переменные окружения

## Запуск

```bash
pip install -r requirements.txt
uvicorn server:app --port 8000
```

Открыть в браузере: http://localhost:8000

## Переменные окружения (.env)

```
OPENAI_API_KEY=your_key
OPENAI_BASE_URL=https://llm.lambda.coredump.ru/v1
MODEL_NAME=openai/gpt-4o-mini
MAPS_API_KEY=your_2gis_key
```

## Пример запроса

```
тихое кафе для работы, центр Москвы
```
