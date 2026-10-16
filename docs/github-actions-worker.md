# GitHub Actions как бесплатный Linux-worker SPPS

**Решение владельца (2026-10-16):** при $0 и без своего Linux считать через **GitHub Actions** на **публичном** репозитории. Neon — БД, Vercel — фронт (опционально), ПК — разработка.

## Тариф

- Публичный репозиторий + standard GitHub-hosted runners → **минуты Actions бесплатны** ([документация GitHub](https://docs.github.com/en/billing/concepts/product-billing/github-actions)).
- Приватный репо: лимит минут по плану (Free ≈ 2000/мес) — не целевой путь для фри-продукта.

## Что делает worker

1. API (`SONOPLAN_JOBS_BACKEND=github_actions`) при `POST /jobs` вызывает `workflow_dispatch` для `.github/workflows/run-spps-product-job.yml`.
2. Передаёт `export_json` (коробка AABB комнаты + источники/РМ из ревизии) — **Phase 2A**.
3. Runner `ubuntu-22.04` строит `mesh.cbin`/`tetramesh.mbin`/`config.xml`, гоняет **живой** SPPS.
4. Пишет `result_manifest.json` + `job_status.json` в artifact `sonoplan-job-{jobId}`.
5. `GET /api/v1/jobs/{id}` синхронизирует статус и подтягивает artifact (публичный callback URL **не нужен**).

### Честность

- Phase 2A: **AABB-коробка** по контуру (прямоугольник — точно; L/многоугольник — оболочка), не полный экструд + TetGen.
- Материалы: α из `materials` ревизии; горизонтальный `recepteur_surfacique_coupe` → `.csbin` при успехе SPPS (`mapAvailable`).
- Solids (стеллажи/перегородки) в snapshot, **не** в mesh до TetGen.
- Без `export_json` — fallback на fixture `minimal_room` (Phase 1).
- Это не Windows `fixture_replay`: на Actions реально запускается Linux SPPS.
- `executionMode`: `github_actions_pending` → `github_actions_spps`.

## Настройка API (локально / Neon)

В `services/api/.env` (не коммитить токен):

```env
SONOPLAN_JOBS_BACKEND=github_actions
SONOPLAN_GITHUB_TOKEN=github_pat_...   # или classic PAT
SONOPLAN_GITHUB_REPOSITORY=Lewa2424/sonoplan
SONOPLAN_GH_WORKFLOW=run-spps-product-job.yml
SONOPLAN_GH_REF=main
```

### Права токена

Нужно диспатчить workflow и читать artifacts:

- Fine-grained: **Actions** Read and write; **Contents** Read (репозиторий SonoPlan).
- Classic: scope `repo` (для public достаточно `public_repo` + право workflow) — проверьте, что `actions:write` на workflow_dispatch проходит.

Workflow-файл должен уже быть на ветке `SONOPLAN_GH_REF` (обычно `main`).

## Проверка

```bash
# Terminal: API with env above + Neon DATABASE_URL
cd services/api
uvicorn sonoplan_api.main:app --reload --app-dir src --host 127.0.0.1 --port 8000

# UI: создать online-проект → ревизия → Расчёты → Запустить
# Ожидание: status queued/running несколько минут → completed + Lp
# В манифесте: executionMode=github_actions_spps и note про fixture mesh
```

Без токена / при ошибке dispatch: job `failed`, `GITHUB_ACTIONS_DISPATCH_FAILED`.

## Ограничения

- Задержка минут (очередь runners), не интерактивный «мгновенный» расчёт.
- Не рассчитано на массовую параллельную нагрузку.
- Репозиторий должен оставаться публичным для $0.
- Теплокарта (.csbin) по-прежнему отложена.
