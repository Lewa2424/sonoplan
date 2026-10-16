# services/worker

Заготовка Celery-приложения для расчётных заданий SonoPlan.

## Назначение

- Читать задания из очереди (RabbitMQ в `infra/docker-compose.yml`)
- Запускать адаптер → SPPS в изолированном процессе
- Публиковать манифест и файлы в object storage (MinIO/S3)
- Heartbeat, отмена, постпроцессинг

## Сейчас

Только каркас `sonoplan_worker.celery_app`. **Adapter и SPPS ещё не подключены** (STG-01 / STG-04).

Не генерировать фиктивные акустические карты в worker.

## Локальный запуск (после поднятия broker)

```bash
cd services/worker
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"

# Broker из infra/.env.example
set CELERY_BROKER_URL=amqp://sonoplan:sonoplan@localhost:5672//
celery -A sonoplan_worker.celery_app worker --loglevel=info
```

Точка стыковки со STG-01: вызов `engine/adapter` из задачи `run_calculation` (пока заглушка).
