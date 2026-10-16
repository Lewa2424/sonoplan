# services/api

FastAPI `/api/v1` — STG-04: проекты, draft с ETag, ревизии, validate, calculation jobs.

## Реализовано

- `GET /api/v1/health`
- `GET /api/v1/capabilities` — **явно stub**, не подтверждённый реестр SPPS
- `POST/GET /api/v1/projects`
- `GET/PATCH /api/v1/projects/{id}/draft` — ETag / If-Match (412 при mismatch, 428 без If-Match)
- `POST /api/v1/projects/{id}/revisions` → `revisionId`, `snapshotHash`
- `POST /api/v1/revisions/{id}/validate` → errors / warnings
- `POST /api/v1/jobs` — заголовок `Idempotency-Key` обязателен; привязка к `revisionId` + `snapshotHash`
- `GET /api/v1/jobs/{id}` — статус / манифест / код ошибки
- `POST /api/v1/jobs/{id}/cancel`

Состояния job: `created` → `queued` → `running` → `completed` | `failed` | `cancelled`.

Бэкенд исполнения (`SONOPLAN_JOBS_BACKEND`):

| Значение | Поведение |
|----------|-----------|
| `inline` (default) | В процессе API через `engine/adapter`. На Windows — `fixture_replay` (decode pinned CI `.recp`), не живой SPPS. |
| `github_actions` | `workflow_dispatch` → Linux SPPS на GitHub-hosted runner; результат через artifact на `GET /jobs/{id}`. См. [`docs/github-actions-worker.md`](../../docs/github-actions-worker.md). |
| `celery` | RabbitMQ worker (`SONOPLAN_JOBS_INLINE=0` без явного backend). |

Фейковая теплокарта не публикуется.

## База данных

- **Prod / staging:** Neon (hosted PostgreSQL) через `DATABASE_URL`.
- **Локально:** Docker Postgres из `infra/docker-compose.yml` — optional; тот же формат URL без Neon.
- Драйвер: `postgresql+psycopg://…`. Для Neon обязателен `sslmode=require` (psycopg подхватывает SSL).
- Пример Neon (плейсхолдеры, не реальные секреты):
  `postgresql+psycopg://USER:PASSWORD@ep-xxxx.region.aws.neon.tech/neondb?sslmode=require`
- Миграции: Alembic (`alembic upgrade head`) из каталога `services/api` — таблицы `projects` / `drafts` / `revisions` / `jobs`.
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
uvicorn sonoplan_api.main:app --app-dir src --host 127.0.0.1 --port 8000
```

На Windows **не используйте `--reload`**: WatchFiles + kill оставляют orphan `multiprocessing.spawn` на порту 8000 — UI уходит в offline/mock. Перезапуск:

```powershell
powershell -File services/api/scripts/restart-api.ps1
```

OpenAPI UI: `http://127.0.0.1:8000/docs`

## Тесты

```bash
pytest
```

Не подключать SPPS из API напрямую в обход adapter — расчёт идёт через `job_execution` → adapter.
