# GitHub Actions как бесплатный Linux-worker SPPS

**Решение владельца (2026-10-16):** при $0 и без своего Linux считать через **GitHub Actions** на **публичном** репозитории. Neon — БД, Vercel — фронт (опционально), ПК — разработка.

## Тариф

- Публичный репозиторий + standard GitHub-hosted runners → **минуты Actions бесплатны** ([документация GitHub](https://docs.github.com/en/billing/concepts/product-billing/github-actions)).
- Приватный репо: лимит минут по плану (Free ≈ 2000/мес) — не целевой путь для фри-продукта.

## Что делает Phase 1

1. API (`SONOPLAN_JOBS_BACKEND=github_actions`) при `POST /jobs` вызывает `workflow_dispatch` для `.github/workflows/run-spps-product-job.yml`.
2. Runner `ubuntu-22.04` скачивает pinned `spps`, гоняет **живой** SPPS.
3. Пишет `result_manifest.json` + `job_status.json` в artifact `sonoplan-job-{jobId}`.
4. `GET /api/v1/jobs/{id}` синхронизирует статус и подтягивает artifact (публичный callback URL **не нужен** — подходит localhost API).

### Честность Phase 1

Геометрия пока `engine/fixtures/minimal_room`, **не** экспорт вашей ревизии.  
Это не `fixture_replay` (decode на Windows): на Actions реально запускается Linux SPPS.  
`executionMode`: `github_actions_pending` → `github_actions_spps`.

Phase 2 (отдельно): адаптер model/revision → mesh/config → тот же workflow.

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
