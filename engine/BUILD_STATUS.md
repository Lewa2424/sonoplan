# STG-01 build / run status

**Дата проверки хоста:** 2026-10-16  
**Обновление пути сборки:** 2026-10-16 (Docker Desktop → blocked; primary = CI / remote Linux)

## Решение владельца

- Docker Desktop на Windows разработчика **не будет установлен** (сборка ОС 19044, обновить Windows нельзя).
- Обход лицензии Windows / пиратские ISO / патчи Docker под старую Windows — **не рассматриваются**.
- Локальный MVP UI/API (STG-02+) продолжается **без** Docker и без локального SPPS.

## Primary path

| Путь | Статус |
|------|--------|
| **GitHub Actions** (`.github/workflows/build-spps.yml`) | **SUCCESS** run [38867272211](https://github.com/Lewa2424/sonoplan/actions/runs/38867272211); checksum в `PINNED.json` |
| **Remote Linux VPS/VM** (`engine/scripts/build-spps-native.sh`) | Документирован; нужен доступ к VPS |
| Docker Engine на Linux VPS (`build-spps.sh`) | Optional, не Desktop |
| Локальный Docker Desktop | **blocked** |
| Native Windows MSVC/MinGW | **не целевой путь** |

Инструкция: [`docs/engine-build-without-docker.md`](../docs/engine-build-without-docker.md).

## Фактические команды и вывод (хост разработчика)

### `docker --version`

```
Имя "docker" не распознано как имя командлета...
CommandNotFoundException
```

### `wsl --status`

```
Эта версия Windows 10.0.19044.1766 не поддерживает обновленную версию подсистемы Windows для Linux.
Установите необходимое обновление ... или через: https://aka.ms/wslinstall
```

### Сборка SPPS / прогон эталона

- CI native Linux: **SUCCESS** (run `38867272211`); artifact скачан локально в `engine/binaries/spps-ci/` (gitignored).
- SHA-256 `spps`: `c5e30a7b1647ed73b26aae58815914a55cc1785223f954ba7e12b3eda0234eb5` → `PINNED.json`.
- Прогон эталона на этом Windows-хосте **не выполняется** (Linux ELF). Нужен Linux worker/VPS + `SPPS_BIN` + fixtures inputs.

### Адаптер (без бинарника SPPS)

Unit-тесты валидации выходов — OK без Docker. `SPPS_BIN` — см. `engine/adapter/README.md`.

## Осталось для полного STG-01 / stub STG-04

1. ~~Linux-сборка + `binary_checksum`~~ — готово.
2. ~~Заполнить `fixtures/minimal_room/inputs`~~ — официальные `mesh.cbin`/`tetramesh.mbin` из I-Simpa `python_bindings/tests` + адаптированный `config.xml` (см. `inputs/ORIGIN.txt`). Прогон: workflow `run-spps-job.yml`.
3. Worker: выставлять `SPPS_BIN` на Linux CI/VPS (не запускать бинарник на Windows).
4. Golden decode `.recp` + SCI-003 допуск — после первого успешного CI-прогона (не публиковать выдуманные дБ).

**Не блокер для STG-02:** web/API каркас на Windows без SPPS.

## Что уже доказано без бинарника

- Upstream `main()` SPPS всегда `return 0` (фрагмент `sppsNantes.cpp` с pinned commit через raw.githubusercontent.com).
- Адаптер отклоняет `exit_code=0` без выходных файлов (4 unit-теста OK; CLI broken_exit0 → exit 1).
- Закреплён SHA I-Simpa и флаги CMake в `PINNED.json`.

## Следующий шаг

1. Download SPPS: см. [`docs/spps-ci-artifact.md`](../docs/spps-ci-artifact.md).
2. CI: `Run SPPS Job` (`run-spps-job.yml`) — attempt-run + validate-outputs на `minimal_room`.
3. Пересборка inputs: `./engine/scripts/prepare-minimal-room-fixture.sh` (или `.py`).
4. Подключить worker → adapter с `SPPS_BIN` (STG-04).
