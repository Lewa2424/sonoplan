# services/api

FastAPI `/api/v1` — STG-02: проекты, draft с ETag, ревизии, validate.

## Реализовано

- `GET /api/v1/health`
- `GET /api/v1/capabilities` — **явно stub**, не подтверждённый реестр SPPS
- `POST/GET /api/v1/projects`
- `GET/PATCH /api/v1/projects/{id}/draft` — ETag / If-Match (412 при mismatch, 428 без If-Match)
- `POST /api/v1/projects/{id}/revisions` → `revisionId`, `snapshotHash`
- `POST /api/v1/revisions/{id}/validate` → errors / warnings

## База данных

- **Production / compose:** PostgreSQL через `DATABASE_URL` (`postgresql+psycopg://…`).
- Миграции: Alembic (`alembic upgrade head`) из каталога `services/api`.
- **Pytest:** SQLite in-memory через fixture override — только для тестов, не prod-путь.

## Локальный запуск

```bash
cd services/api
python -m venv .venv
# Windows:
.venv\Scripts\activate
pip install -e ".[dev]"
# при поднятом postgres из infra/compose:
# set DATABASE_URL=postgresql+psycopg://sonoplan:sonoplan@localhost:5432/sonoplan
# alembic upgrade head
uvicorn sonoplan_api.main:app --reload --app-dir src
```

OpenAPI UI: `http://127.0.0.1:8000/docs`

## Тесты

```bash
pytest
```

Не подключать SPPS из API напрямую — только через worker → adapter.
