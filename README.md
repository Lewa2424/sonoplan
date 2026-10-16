# SonoPlan

Мобильное PWA для предварительного акустического проектирования производственных помещений.

Расчёт выполняется серверным ядром SPPS (через адаптер). Браузер не обращается к очереди, БД или SPPS напрямую.

## Структура (DEV-002)

| Путь | Назначение |
|------|------------|
| `apps/web` | мобильный интерфейс (React + Vite + TS) |
| `services/api` | FastAPI, draft/revisions/jobs |
| `services/worker` | Celery, изоляция заданий |
| `packages/domain` | типы модели, единицы, координаты |
| `packages/contracts` | JSON Schema / OpenAPI |
| `engine/adapter` | перевод модели ↔ SPPS *(STG-01)* |
| `engine/patches` | минимальные патчи ядра |
| `engine/fixtures` | эталонные входы/выходы |
| `infra` | Docker Compose и окружение |
| `tests/e2e` | сквозные сценарии |
| `docs` | ТЗ, решения, списки изменений |

## Требования окружения

- Node.js LTS ≥ 20, **pnpm** 9.x
- Python ≥ 3.11 (api/worker)
- Docker Engine + Compose (инфраструктура)
- На Windows для сборки SPPS предпочтителен WSL2

## Быстрый старт (каркас)

```bash
# JS-пакеты
pnpm install
pnpm --filter @sonoplan/domain test
pnpm --filter @sonoplan/web dev

# Python API (из services/api)
python -m venv .venv
# Windows: .venv\Scripts\activate
pip install -e ".[dev]"
uvicorn sonoplan_api.main:app --reload --app-dir src

# Инфраструктура (позже, когда сервисы не stub)
cd infra
cp .env.example .env
docker compose up -d postgres rabbitmq minio
```

Compose поднимает PostgreSQL, RabbitMQ и MinIO (S3-совместимое хранилище). Сервисы `api`/`worker`/`web` в compose помечены как stubs до готовности образов.

## Стадии MVP

- **STG-01** — воспроизводимый путь SPPS (`engine/`)
- **STG-02** — схема проекта, единицы, координаты, ревизии, минимальный API
- **STG-03…** — редактор и связка с расчётом

Не выдавать интерполяцию/палитру за физический расчёт. Не подменять SPPS заранее нарисованной картой.

## Источник требований

`TZ_mobilnoe_veb_prilozhenie_akustika.docx` и правила в `.cursor/rules/`.
