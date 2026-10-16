# services/worker

Celery-приложение для расчётных заданий SonoPlan (STG-04).

## Назначение

- Читать задания из очереди (RabbitMQ в `infra/docker-compose.yml`)
- Запускать `engine/adapter` → SPPS в изолированном процессе
- Обновлять статус job в PostgreSQL (`failed` с кодом, если нет `SPPS_BIN` / не Linux)
- Не публиковать фиктивные акустические карты

## Поведение `sonoplan.run_calculation`

1. Загружает `jobs` row по `job_id`
2. `check_spps_environment()` — на Windows / без `SPPS_BIN` → `failed` (`SPPS_NOT_LINUX` / `SPPS_BIN_MISSING`)
3. `attempt_spps_calculation` на workdir (по умолчанию `engine/fixtures/minimal_room/inputs`)
4. При отсутствии `config.xml` → `FIXTURE_INPUTS_MISSING` (блокер fixture, не фейковый result)

## Env

| Переменная | Назначение |
|------------|------------|
| `CELERY_BROKER_URL` | RabbitMQ |
| `DATABASE_URL` | та же БД, что у API |
| `SPPS_BIN` | абсолютный путь к Linux `spps` |
| `SONOPLAN_SPPS_WORK_DIR` | опционально: workdir вместо fixture inputs |
| `SONOPLAN_JOBS_INLINE` | на стороне API: `1` (default) = выполнить в процессе API без Celery |

Linux SPPS: checksum в `engine/PINNED.json`. На Windows-хосте разработчика ELF не запускать.

## Локальный запуск

```bash
cd services/worker
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
# также нужен editable API + adapter на PYTHONPATH (см. monorepo layout)
pip install -e ../api

set CELERY_BROKER_URL=amqp://sonoplan:sonoplan@localhost:5672//
set DATABASE_URL=postgresql+psycopg://sonoplan:sonoplan@localhost:5432/sonoplan
celery -A sonoplan_worker.celery_app worker --loglevel=info
```

Для локальной разработки без RabbitMQ API по умолчанию использует inline-исполнение (`SONOPLAN_JOBS_INLINE=1`).
