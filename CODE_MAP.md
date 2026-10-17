# CODE_MAP — SonoPlan

Карта структуры репозитория (STG-04). Не changelog.

## Назначение продукта

Мобильное PWA предварительного акустического проектирования производственных помещений. Расчёт — серверное ядро SPPS через адаптер; GUI I-Simpa в веб не переносится.

## Потоки

```
apps/web  →  HTTPS JSON /api/v1  →  services/api
                                      ↓ publish job (inline или Celery)
                               services/worker
                                      ↓
                               engine/adapter  →  SPPS (отдельный процесс, Linux)
                                      ↓
                         ResultManifest + файлы → S3/MinIO (позже)
                                      ↓
apps/web ← GET /jobs/{id} (status / manifest; без фейковой карты)
```

Браузер не ходит в очередь, БД или SPPS напрямую.

CI-путь без Docker Desktop: `.github/workflows/run-spps-job.yml` скачивает Linux `spps`, гоняет adapter на fixture, грузит report-artifact.

## Директории и значимые файлы

| Путь | Роль |
|------|------|
| `apps/web` | React+Vite+TS; редактор цеха (Konva) + экран «Расчёты» |
| `apps/web/src/api` | fetch-клиент `/api/v1`, ETag/If-Match, jobs |
| `apps/web/src/pages/CalculationsPage.tsx` | job + polling; таблица punctual Lp (дБ) и LA (дБА); карта SPPS в дБА |
| `apps/web/src/store/editorStore.ts` | Zustand: модель, selection, sync, validate, revision |
| `apps/web/src/model/surfaceMapValidity.ts` | Правдоподобие сетки SPPS (заполнение ≥45 %, охват ≥90 %), наличие `laDb` и рамки `exportMeta`; `surfaceMapFromManifest` → сетка в координатах проекта |
| `apps/web/src/model/lpPalette.ts` / `components/NoiseScaleLegend.tsx` | Фиксированная шкала дБА (≤60…>105, цвета DIN 45682 +30 дБ) для карты SPPS и оценки |
| `packages/domain` | Типы; координаты; геометрия; `computeSnapshotHash`; `validateModel` |
| `packages/domain/src/diffuseFieldEstimate.ts` | Предварительная оценка Lp/LA по формуле помещения (OPT-010), не SPPS; ᾱ по площади пола/стен/потолка; слой «Оценка» на плане |
| `packages/domain/src/schemaMigration.ts` / `roomSurfaces.ts` | Миграция схемы 1.0 → 1.1; площади и материалы групп ограждений |
| `packages/domain/src/soundPower.ts` | Суммарный LwA по октавам Lw; ровный спектр по заданному LwA |
| `packages/domain/src/aWeighting.ts` / `planCut.ts` | A-коррекция октав (IEC 61672-1); высота среза плана — паритет с `export_revision._coupe_z_away_from_sources` |
| `packages/contracts` | `schemas/project.schema.json`, `openapi/openapi.yaml`, `SCHEMA_VERSION` |
| `services/api` | FastAPI: projects/draft/revisions/validate/**jobs** |
| `services/api/scripts/restart-api.ps1` | Windows: kill port-8000 orphans, start uvicorn **without** `--reload` |
| `services/api/src/sonoplan_api/job_execution.py` | inline/worker: adapter → fail codes / ResultManifest |
| `services/api/src/sonoplan_api/github_actions_jobs.py` | Free Linux worker: dispatch + poll Actions artifacts |
| `.github/workflows/run-spps-product-job.yml` | Product job: live SPPS on ubuntu-22.04 → job artifact |
| `engine/adapter/sonoplan_adapter/export_revision.py` | Phase 2A: AABB box; Phase 3A: AABB solids → Kuhn holes; α по поверхностям (`type_surface` пол=1 / стены=0 / потолок=2 / obstacle=3) + coupe + sources/РМ |
| `engine/adapter/sonoplan_adapter/aabb_obstacle_mesh.py` | Phase 3A: ось-выровненные solids → conforming cbin/mbin без внешнего TetGen |
| `engine/adapter/sonoplan_adapter/cbin_io.py` / `mbin_io.py` | In-place scale official cube (пусто); write_cbin/write_mbin для Phase 3A пары |
| `engine/adapter/sonoplan_adapter/rsbin_io.py` | ENG-006: decode coupe `.csbin` → grid по порядку записи SPPS (индексы граней Linux-SPPS усечены), уровень 10·lg(E/1e-12) как в I-Simpa |
| `engine/adapter/sonoplan_adapter/weighting.py` | A-weighting по энергии полос; `laDb` карты из `recepteurss/<f> Hz/` со сверкой с Global (≤0.5 дБ) |
| `apps/web/src/model/materialCatalog.ts` / `equipmentCatalog.ts` | Каталог покрытий (октавные α, akustik.ua/BRE, `mvp-2`) и оборудования (суммарный LwA) |
| `docs/github-actions-worker.md` | Setup PAT / env for Actions backend |
| `services/api/alembic` | `projects` / `drafts` / `revisions` / **`jobs`** |
| `services/worker` | Celery `sonoplan.run_calculation` → `execute_job` |
| `engine/adapter` | env gates, runner, validate_outputs, GABE/.recp decode, `attempt-run` / `decode-outputs` CLI |
| `engine/fixtures/minimal_room` | scaffold inputs (блокер полного прогона ядра) |
| `engine/PINNED.json` | I-Simpa commit + `binary_checksum` + artifact run id |
| `.github/workflows/build-spps.yml` | сборка Linux SPPS |
| `.github/workflows/run-spps-job.yml` | download artifact → adapter attempt → decode-outputs → ResultManifest artifact |
| `infra/docker-compose.yml` | optional local postgres, rabbitmq, minio; api/worker/web — profile stubs |
| `infra/.env.example` | шаблон env; prod/staging Postgres = Neon (`sslmode=require`) |
| `docs/` | ТЗ-выписки, `CHANGED_FILES.txt`, `spps-energy-blocker.md`, `spps-ci-artifact.md`, Neon |
| `.cursor/rules/` | правила Cursor / SonoPlan |

## Точки входа

| Слой | Вход |
|------|------|
| Web | `apps/web/src/main.tsx` → `pnpm --filter @sonoplan/web dev` (порт 5173) |
| API | `services/api/src/sonoplan_api/main.py` → `uvicorn sonoplan_api.main:app --reload --app-dir src` (порт 8000) |
| Worker | `services/worker/src/sonoplan_worker/celery_app.py` |
| Adapter CLI | `python -m sonoplan_adapter.cli` из `engine/adapter` |
| Domain | `@sonoplan/domain` → `packages/domain/src/index.ts` |
| Contracts | `@sonoplan/contracts` + YAML/JSON Schema файлы |
| Compose | `infra/docker-compose.yml` |
| Миграции API | `services/api` → `alembic upgrade head` (нужен PostgreSQL) |

### База данных

- **Целевой Postgres (prod/staging):** Neon (hosted). URL: `postgresql+psycopg://…?sslmode=require` — см. `infra/.env.example`.
- **Локально:** Docker Postgres из compose — optional (удобно для Alembic/ручных прогонов).
- **Тесты API:** SQLite in-memory только через pytest fixture; не использовать как runtime-путь.

### Локальный подъём API + Web

```bash
# Terminal 1 — API
cd services/api
.venv\Scripts\activate
uvicorn sonoplan_api.main:app --reload --app-dir src --host 127.0.0.1 --port 8000

# Terminal 2 — Web
pnpm --filter @sonoplan/web dev
```

Клиент: `VITE_API_BASE_URL=http://127.0.0.1:8000`.  
Jobs по умолчанию inline (`SONOPLAN_JOBS_INLINE=1`). На Windows без Linux SPPS —
fixture_replay (decode `expected/*.recp`); отключить: `SONOPLAN_SPPS_FIXTURE_REPLAY=0`.

## Экраны Web

| Маршрут | Содержимое |
|---------|------------|
| `/projects` | Список/создание через API; offline-черновик с явной пометкой |
| `/model`, `/model/:projectId` | План Konva, свойства, validate, revision, draft ETag sync |
| `/calculations` | Job по ревизии + polling; таблица punctual Lp при наличии; без теплокарты и фейковых дБ |

## Владельцы состояния и источники истины

| Данные | Владелец | Примечание |
|--------|----------|------------|
| Черновик модели (online) | API `drafts` + ETag | PATCH + If-Match; 412 → конфликт в UI |
| Черновик (offline) | Zustand в памяти | Явная пометка; не выдаётся за серверный |
| Ревизия на расчёт | API `revisions.snapshot` | Неизменяема; `snapshotHash` |
| Job | API `jobs` | `revisionId` + `snapshotHash`; Idempotency-Key |
| UI selection / toolMode / camera | Zustand `editorStore` | Не входят в snapshotHash |
| Результат | Worker/adapter → `result_manifest` | punctual energy p²-homogeneous; при energy=0 → `lpDb=null` (не 0 дБ); `mapAvailable` только после surface decode; Windows MVP: `executionMode=fixture_replay` из `expected/` |
| Возможности ядра | `GET /capabilities` | **stub** |
| Координаты / геометрия | `packages/domain` | X,Y пол, Z вверх; Three = X,Z,−Y |

## Публичные контракты

- Префикс `/api/v1`; OpenAPI в `packages/contracts`
- `schemaVersion`: `"1.1"` (пишется); `"1.0"` читается — `migrateModelSnapshot`: `room.materialVersionId` → `surfaceMaterials` пола/стен/потолка; ревизии 1.0 в БД не переписываются
- Jobs: `POST /jobs` (+ `Idempotency-Key`), `GET /jobs/{id}`, `POST /jobs/{id}/cancel`
- Коды отказа ядра: `SPPS_NOT_LINUX`, `SPPS_BIN_MISSING`, `FIXTURE_INPUTS_MISSING`, …
- Клиентские env: только `VITE_*`
- CORS: API разрешает `localhost:5173` / `127.0.0.1:5173`, expose `ETag`

## Тесты и эталоны

| Что | Где |
|-----|-----|
| Координаты / контур / snapshotHash / validate | `packages/domain` vitest |
| UI contour helpers | `apps/web/src/model/contourHelpers.test.ts` |
| API draft / revision / **jobs idempotency + states** | `services/api/tests` |
| Adapter validate_outputs / env gates | `engine/adapter/tests` |
| E2E | `tests/e2e` *(заглушка)* |

## Критические инварианты

- Lw ≠ Lp; спектр источника — `powerSpectrumLw` (quantity sound_power)
- Координаты: проект X,Y,Z; не путать с экранными
- Ревизия неизменяема; камера/палитра не запускают пересчёт
- Не подменять SPPS заранее нарисованной картой; не выдумывать дБ
- Exit 0 SPPS без валидных выходов → failed
- Capabilities stub ≠ подтверждённые возможности ядра
- Базовый SPPS не заявляет дифракцию/интерференцию/моды
- PII/секреты не логировать и не коммитить

## Блокер акустики

**CLOSED** — см. `docs/spps-energy-blocker.md`. CI fixture даёт ненулевую punctual энергию и Lp.
Windows UI показывает уровни через fixture_replay; живой SPPS — Linux worker / CI.
