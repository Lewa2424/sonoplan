# CODE_MAP — SonoPlan

Карта структуры репозитория (DEV-002 / STG-02). Не changelog.

## Назначение продукта

Мобильное PWA предварительного акустического проектирования производственных помещений. Расчёт — серверное ядро SPPS через адаптер; GUI I-Simpa в веб не переносится.

## Потоки

```
apps/web  →  HTTPS JSON /api/v1  →  services/api
                                      ↓ publish job
                               services/worker
                                      ↓
                               engine/adapter  →  SPPS (отдельный процесс)
                                      ↓
                         ResultManifest + файлы → S3/MinIO
                                      ↓
apps/web ← API (manifest / samples / slices)
```

Браузер не ходит в очередь, БД или SPPS напрямую.

## Директории и значимые файлы

| Путь | Роль |
|------|------|
| `apps/web` | React+Vite+TS скелет, словари `src/i18n/ru.ts`, экраны-заглушки |
| `packages/domain` | Типы Project/Revision/Room/Source/Workplace/MaterialVersion/Solid; координаты; геометрия контура; `computeSnapshotHash`; `validateModel` |
| `packages/contracts` | `schemas/project.schema.json`, `openapi/openapi.yaml`, `SCHEMA_VERSION` |
| `services/api` | FastAPI: health, capabilities stub, projects/draft/revisions/validate; SQLAlchemy + Alembic |
| `services/api/alembic` | Миграция `projects` / `drafts` / `revisions` (PostgreSQL) |
| `services/worker` | Celery app stub; задача `sonoplan.run_calculation` без акустики |
| `engine/adapter` | адаптер SPPS (зона STG-01; не перезаписывать из web/API) |
| `engine/patches` | патчи ядра (STG-01) |
| `engine/fixtures` | эталоны входов/выходов (STG-01) |
| `engine/scripts`, `Dockerfile`, `PINNED.json` | сборка/пины ядра (STG-01) |
| `infra/docker-compose.yml` | postgres, rabbitmq, minio; api/worker/web — profile stubs |
| `infra/.env.example` | `DATABASE_URL` → PostgreSQL; без production-секретов |
| `tests/e2e` | заглушка под сквозные сценарии |
| `docs/` | ТЗ-выписки, `CHANGED_FILES.txt` |
| `.cursor/rules/` | правила Cursor / SonoPlan |

## Точки входа

| Слой | Вход |
|------|------|
| Web | `apps/web/src/main.tsx` → `pnpm --filter @sonoplan/web dev` |
| API | `services/api/src/sonoplan_api/main.py` → `uvicorn sonoplan_api.main:app` |
| Worker | `services/worker/src/sonoplan_worker/celery_app.py` |
| Domain | `@sonoplan/domain` → `packages/domain/src/index.ts` |
| Contracts | `@sonoplan/contracts` + YAML/JSON Schema файлы |
| Compose | `infra/docker-compose.yml` |
| Миграции API | `services/api` → `alembic upgrade head` (нужен PostgreSQL) |

## Владельцы состояния и источники истины

| Данные | Владелец | Примечание |
|--------|----------|------------|
| Черновик модели | API `drafts` + ETag | Изменяемый; PATCH требует If-Match |
| Ревизия на расчёт | API `revisions.snapshot` | Неизменяема; `snapshotHash` = SHA-256 канонического JSON модели |
| Результат | Worker → storage + ResultManifest | Привязан к revisionId (ещё не реализован) |
| Возможности ядра | engine/adapter registry → `GET /capabilities` | Сейчас **stub** |
| Координаты / геометрия | `packages/domain` | X,Y пол, Z вверх; Three = X,Z,−Y; контур: замкнутость + самопересечение |

ТЗ: `TZ_mobilnoe_veb_prilozhenie_akustika.docx`. После появления кода — код, lock-файлы, схемы, эталоны.

## Публичные контракты

- Префикс `/api/v1`; перечень путей — `packages/contracts` (OpenAPI + `API_V1_PATHS`)
- `schemaVersion`: `"1.0"`
- Реализовано STG-02: `POST/GET /projects`, `GET/PATCH .../draft` (ETag/If-Match), `POST .../revisions`, `POST /revisions/{id}/validate`
- Idempotency-Key на `POST /jobs` (ещё не реализован)
- ResultManifest (ещё не реализован)
- Клиентские публичные env: только `VITE_*`
- БД: `DATABASE_URL` → PostgreSQL (`postgresql+psycopg://…`). SQLite — только pytest fixture, не prod.

## Зависимости и лицензионные границы

- Web: React, Vite, TypeScript, pnpm workspace
- API: FastAPI, Pydantic, SQLAlchemy, Alembic, psycopg
- Worker: Celery
- Infra: PostgreSQL, RabbitMQ, MinIO
- Engine: SPPS / I-Simpa / TetGen — **вне этого каркаса**; лицензии GPLv3/AGPL/TetGen учитывать в STG-01
- Не добавлять UI-kit сверх скелета без отдельного решения

## Тесты и эталоны

| Что | Где |
|-----|-----|
| Координаты / null≠0 / контур / snapshotHash / validate | `packages/domain` vitest |
| API health/capabilities / draft conflict / revision | `services/api/tests` (SQLite in-memory fixture) |
| SPPS fixtures | `engine/fixtures` *(STG-01)* |
| E2E | `tests/e2e` *(заглушка)* |

## Критические инварианты

- Lw ≠ Lp; дБ только по энергии; A-коррекция один раз к невзвешенным полосам
- Координаты: проект X,Y,Z; Three.js = X, Z, −Y одной функцией в domain
- Ревизия на расчёте неизменяема; камера/палитра не запускают пересчёт
- `snapshotHash` не зависит от имени проекта и камеры
- Незамкнутый контур / самопересечение / источник в solid / пустой спектр Lw — блокирующие ошибки validate
- Оценочные материалы (`estimated`) — warning
- Не подменять SPPS заранее нарисованной картой
- Неизвестное = `null` + причина, не `0`
- Capabilities stub ≠ подтверждённые возможности ядра
- PII/секреты не логировать и не коммитить
