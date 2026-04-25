# Источники данных

## 2GIS Places API

- **Провайдер:** 2GIS (ДубльГИС)
- **Endpoint:** https://catalog.api.2gis.com/3.0/items
- **Дата интеграции:** апрель 2026
- **Тип ключа:** демо, 1000 запросов в месяц
- **Что возвращает:** название, адрес, координаты, рейтинг, расписание, категории, описание
- **Ограничения:** нет текстовых отзывов и фото на демо-ключе
- **Формат данных:** JSON → Pydantic модель `Place`

### Поля ответа (`GET /3.0/items`)

| Поле API | Поле модели | Описание |
|---|---|---|
| `name` | `name` | Название заведения |
| `address_name` | `address` | Адрес одной строкой |
| `point.lat/lon` | `lat`, `lon` | Координаты |
| `rating` | `rating` | Рейтинг 0–5 |
| `schedule` | `hours` | Расписание по дням |
| `description` | `description` | Описание от владельца |
| `rubrics[].name` | `rubrics` | Категории места |

### Дополнительные данные (`GET /3.0/items/byid`)

| Поле API | Поле модели | Описание |
|---|---|---|
| `reviews.general_review_count` | `reviews_count` | Число отзывов |
| `photos.count` | `photos_count` | Число фото |
| `contact_groups` | `phone`, `website` | Контакты |
| `price_comment` | `price_level` | Ценовой уровень |

## Структура сохранённых данных

Каждый поисковый запрос сохраняется в `data/results/search_TIMESTAMP.json`.

```json
{
  "query": "тихое кафе для работы",
  "timestamp": "2026-04-24T15:30:00",
  "source": "2GIS Places API",
  "source_url": "https://catalog.api.2gis.com/3.0/items",
  "results_count": 10,
  "places": [ ... ]
}
```

## Примеры данных

`data/results/` — реальные результаты поисков с датой и источником.
