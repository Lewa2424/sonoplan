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

## Быстрый старт: API + Web (локально)

Нужны: Node.js LTS ≥ 20, **pnpm** 9.x, Python ≥ 3.11.  
База: Neon через `services/api/.env` (`DATABASE_URL`, не коммитить) — см. `docs/neon-postgres.md`.

```bash
# Один раз: зависимости
pnpm install
cd services/api
python -m venv .venv
# Windows:
.venv\Scripts\activate
pip install -e ".[dev]"
# alembic upgrade head   # если схема ещё не накатана на Neon

# Terminal 1 — API (порт 8000), из services/api с активированным .venv
uvicorn sonoplan_api.main:app --reload --app-dir src --host 127.0.0.1 --port 8000

# Terminal 2 — Web (порт 5173), из корня репо
pnpm --filter @sonoplan/web dev
```

Открыть: `http://127.0.0.1:5173` (API docs: `http://127.0.0.1:8000/docs`).  
Клиент ждёт `VITE_API_BASE_URL=http://127.0.0.1:8000` (по умолчанию в web).

Опционально локальный Postgres/RabbitMQ/MinIO: `infra/docker-compose.yml` (api/web в compose — stubs).

## Стадии MVP

- **STG-01** — воспроизводимый путь SPPS (`engine/`); Build CI; **energy blocker paused** — `docs/spps-energy-blocker.md`
- **STG-02** — схема проекта, единицы, координаты, ревизии, минимальный API
- **STG-03** — мобильный редактор цеха (план Konva, draft ETag, validate/revision)
- **STG-04** — `POST/GET /jobs` + cancel, worker→adapter, CI `run-spps-job.yml`; экран «Расчёты» без теплокарты и без фейковых дБ

Не выдавать интерполяцию/палитру за физический расчёт. Не подменять SPPS заранее нарисованной картой.

## Источник требований

`TZ_mobilnoe_veb_prilozhenie_akustika.docx` и правила в `.cursor/rules/`.
