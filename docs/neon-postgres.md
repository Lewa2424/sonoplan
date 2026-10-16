# Neon как целевой PostgreSQL

Целевая БД для **prod / staging** — [Neon](https://neon.tech) (hosted PostgreSQL).

| Среда | Хранилище |
|-------|-----------|
| prod / staging | Neon |
| локальная разработка | Docker Postgres в `infra/docker-compose.yml` (optional) |
| pytest (`services/api`) | SQLite in-memory через fixture — только тесты |

URL для SQLAlchemy + psycopg (плейсхолдеры):

```text
postgresql+psycopg://USER:PASSWORD@ep-xxxx.region.aws.neon.tech/neondb?sslmode=require
```

`sslmode=require` обязателен для Neon. Реальные credentials не коммитить — только `infra/.env` / секреты хостинга.

См. также: `infra/.env.example`, `services/api/README.md`, `CODE_MAP.md`.
