# CODE_MAP — SonoPlan

Карта структуры репозитория (STG-02 / STG-03). Не changelog.

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
| `apps/web` | React+Vite+TS PWA-скелет; **STG-03** редактор цеха (Konva план, draft sync) |
| `apps/web/src/api` | fetch-клиент `/api/v1`, ETag/If-Match, ошибки связи |
| `apps/web/src/store/editorStore.ts` | Zustand: модель, selection, sync, validate, revision |
| `apps/web/src/model/contourHelpers.ts` | прямоугольник / L / замыкание контура (vitest) |
| `apps/web/src/components/PlanCanvas.tsx` | React Konva план сверху |
| `packages/domain` | Типы Project/Revision/Room/Source/Workplace; координаты; геометрия; `computeSnapshotHash`; `validateModel` |
| `packages/contracts` | `schemas/project.schema.json`, `openapi/openapi.yaml`, `SCHEMA_VERSION` |
| `services/api` | FastAPI: health, capabilities stub, projects/draft/revisions/validate; CORS dev для Vite |
| `services/api/alembic` | Миграция `projects` / `drafts` / `revisions` (PostgreSQL) |
| `services/worker` | Celery app stub; задача `sonoplan.run_calculation` без акустики |
| `engine/*` | адаптер/патчи/fixtures/скрипты SPPS (STG-01) |
| `infra/docker-compose.yml` | postgres, rabbitmq, minio; api/worker/web — profile stubs |
| `tests/e2e` | заглушка под сквозные сценарии |
| `docs/` | ТЗ-выписки, `CHANGED_FILES.txt` |
| `.cursor/rules/` | правила Cursor / SonoPlan |

## Точки входа

| Слой | Вход |
|------|------|
| Web | `apps/web/src/main.tsx` → `pnpm --filter @sonoplan/web dev` (порт 5173) |
| API | `services/api/src/sonoplan_api/main.py` → `uvicorn sonoplan_api.main:app --reload --app-dir src` (порт 8000) |
| Worker | `services/worker/src/sonoplan_worker/celery_app.py` |
| Domain | `@sonoplan/domain` → `packages/domain/src/index.ts` |
| Contracts | `@sonoplan/contracts` + YAML/JSON Schema файлы |
| Compose | `infra/docker-compose.yml` |
| Миграции API | `services/api` → `alembic upgrade head` (нужен PostgreSQL) |

### Локальный подъём API + Web (STG-03)

```bash
# Terminal 1 — API (нужен PostgreSQL или тестовый путь из README)
cd services/api
.venv\Scripts\activate   # Windows
uvicorn sonoplan_api.main:app --reload --app-dir src --host 127.0.0.1 --port 8000

# Terminal 2 — Web
pnpm --filter @sonoplan/web dev
```

Клиент по умолчанию: `VITE_API_BASE_URL=http://127.0.0.1:8000` (`apps/web/.env.example`).  
Если API недоступен — экран «Проекты» предлагает **локальный черновик (offline)** только для UI; PATCH/ревизии недоступны.

## Экраны Web (STG-03)

| Маршрут | Содержимое |
|---------|------------|
| `/projects` | Список/создание через API; offline-черновик с явной пометкой |
| `/model`, `/model/:projectId` | План Konva, свойства, validate, revision, draft ETag sync |
| `/calculations` | Stub: нужен серверный SPPS + ревизия; **без** тепловой карты |

## TODO (не сделано в STG-03)

- **3D-вид** комнаты (Three.js / R3F, коробка без акустики) — орто-план достаточен; вкладка «3D» disabled
- Jobs / ResultManifest / очередь расчёта — **STG-04** (когда появится бинарник SPPS)
- Dexie offline persistence, vite-plugin-pwa полный offline, i18n uk/en
- Playwright e2e smoke (есть vitest на contour helpers)

## Владельцы состояния и источники истины

| Данные | Владелец | Примечание |
|--------|----------|------------|
| Черновик модели (online) | API `drafts` + ETag | PATCH + If-Match; 412 → конфликт в UI |
| Черновик (offline) | Zustand в памяти | Явная пометка; не выдаётся за серверный |
| Ревизия на расчёт | API `revisions.snapshot` | Неизменяема; `snapshotHash` |
| UI selection / toolMode / camera | Zustand `editorStore` | Не входят в snapshotHash |
| Результат | Worker → storage + ResultManifest | STG-04 |
| Возможности ядра | `GET /capabilities` | **stub** |
| Координаты / геометрия | `packages/domain` | X,Y пол, Z вверх; Three = X,Z,−Y |

## Публичные контракты

- Префикс `/api/v1`; OpenAPI в `packages/contracts`
- `schemaVersion`: `"1.0"`
- STG-02: `POST/GET /projects`, `GET/PATCH .../draft` (ETag/If-Match), `POST .../revisions`, `POST /revisions/{id}/validate`
- Клиентские env: только `VITE_*`
- CORS: API разрешает `localhost:5173` / `127.0.0.1:5173`, expose `ETag`

## Зависимости Web (STG-03)

- React 18, Vite, TypeScript, react-router-dom
- **react-konva@18** + **konva@9**, **zustand**, **@tanstack/react-query**
- vitest (contour helpers)
- Three/R3F — **не подключены** (TODO выше)

## Тесты и эталоны

| Что | Где |
|-----|-----|
| Координаты / контур / snapshotHash / validate | `packages/domain` vitest |
| UI contour helpers | `apps/web/src/model/contourHelpers.test.ts` |
| API draft conflict / revision | `services/api/tests` |
| E2E | `tests/e2e` *(заглушка)* |

## Критические инварианты

- Lw ≠ Lp; спектр источника — `powerSpectrumLw` (quantity sound_power)
- Координаты: проект X,Y,Z; не путать с экранными
- Ревизия неизменяема; камера/палитра не запускают пересчёт
- Не подменять SPPS заранее нарисованной картой
- Capabilities stub ≠ подтверждённые возможности ядра
- PII/секреты не логировать и не коммитить

## Готовность к STG-04

Редактор умеет зафиксировать ревизию и показать `snapshotHash`.  
Очередь `POST /jobs` + worker + SPPS — следующий этап **только когда** есть бинарник/адаптер; UI расчётов остаётся stub до этого.
