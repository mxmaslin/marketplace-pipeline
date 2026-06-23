# AI Usage Log

Документ описывает, как использовался ИИ-агент (Cursor) при выполнении тестового задания.

## Исходный запрос

Реализовать пайплайн из `vision.md`: парсинг маркетплейса, LLM-классификация, интеграция с CRM, pytest ≥70%, Docker, CI, README.

## Архитектурные решения (согласованы с кандидатом)

| Решение | Обоснование |
|---------|-------------|
| Ozon + OpenAI + AmoCRM | Соответствует стеку вакансии Интерика Лаб |
| `MOCK_PARSER` как env-флаг | Явное требование кандидата; симметрично `MOCK_LLM` / `MOCK_CRM` |
| Partial collection OK | Если категория исчерпана до 10K — не ошибка |
| Demo 100 товаров | Быстрая локальная проверка; код масштабируется на 10K |
| Батчинг LLM (`LLM_BATCH_SIZE=25`) | Снижает число запросов с 10K до ~400 |
| Стандарт не в CRM | Классифицируется, но задачи только для Premium/Economy |
| CRM идемпотентность | SHA-256(title+description), local store + маркер в AmoCRM |

## Промпты / задачи агенту

1. «Изучи vision.md, найди discrepancies» — анализ ТЗ, список неоднозначностей.
2. «Proceed with implementation» — полная генерация проекта после уточнения трактовок.
3. «Нужна идемпотентность CRM» — store + remote reconcile по маркеру.

## Сгенерировано ИИ

- Структура пакета `marketplace_pipeline/`
- Pydantic-модели и settings
- `HttpClient` с tenacity (429 + exponential backoff)
- `OzonParser`, `MockParser`, factory
- `SegmentClassifier` с batch-промптом OpenAI
- `AmoCRMClient`, selectors, `Pipeline`
- pytest + pytest-httpx
- Dockerfile, docker-compose, GitHub Actions
- README, .env.example, AI_USAGE.md

## Исправлено / уточнено вручную (кандидатом)

- Partial collection: OK если нет больше записей в категории
- Mock парсера — только env-флаг, не отдельный сервис
- CRM: сортировка по `price` **внутри** LLM-сегмента
- Demo mode для локальных прогонов
- Идемпотентность CRM обязательна (повторный прогон → `reused=true`)

## Батчинг LLM — как решалось

```
Промпт (system): классифицируй items, верни JSON [{id, segment}]
Промпт (user): {"items": [{id, name, description}, ...]}  # до 25 штук
Ответ: {"items": [{"id":"...", "segment":"Эконом|Стандарт|Премиум"}]}
Fallback: если id пропущен или segment невалиден → «Стандарт»
MOCK_LLM: эвристика по ключевым словам и price thresholds
```

## Что стоит проверить ревьюеру

- [ ] Coverage ≥95% (`pytest`)
- [ ] `docker compose up --build` с mock-флагами
- [ ] Логи partial/degraded collection
- [ ] Формат описания CRM-задач (URL + цена)
- [ ] Повторный прогон не дублирует CRM-задачи (`reused=true` в логах)

## Ограничения автогенерации

ИИ не запускал реальный сбор 10K с Ozon и не создавал задачи в боевой AmoCRM — для этого нужны ключи и устойчивый доступ к API.
