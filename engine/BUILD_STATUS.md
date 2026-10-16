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
| **GitHub Actions** (`.github/workflows/build-spps.yml`) | Готов в репо; нужен git remote + запуск |
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

**Не запускались** на этом хосте — нет Docker Desktop и нет готового Linux runner.  
CI workflow и native-скрипт **добавлены**, но артефакт бинарника ещё не получен.

### Адаптер (без бинарника SPPS)

Unit-тесты валидации выходов — OK без Docker (см. отчёт worker / adapter).

## Блокер до первого артефакта SPPS

1. Нет выполненной Linux-сборки (нужен GitHub remote + Actions **или** Ubuntu VPS).
2. Локальный `git clone` I-Simpa в этот workspace блокировался Cursor Hooks; clone выполняется в CI/VPS / в Docker-на-Linux.
3. ENG-002 (сборка) и эталонный прогон закрываются только после artifact + inputs fixtures.

**Не блокер для STG-02:** web/API каркас на Windows без SPPS.

## Что уже доказано без бинарника

- Upstream `main()` SPPS всегда `return 0` (фрагмент `sppsNantes.cpp` с pinned commit через raw.githubusercontent.com).
- Адаптер отклоняет `exit_code=0` без выходных файлов (4 unit-теста OK; CLI broken_exit0 → exit 1).
- Закреплён SHA I-Simpa и флаги CMake в `PINNED.json`.

## Следующий шаг после появления Linux runner

1. Запустить `Build SPPS` (Actions) или `./engine/scripts/build-spps-native.sh` на VPS.
2. Скачать artifact; сверить `SHA256SUMS`.
3. Записать `binary_checksum` в `PINNED.json`.
4. Заполнить `fixtures/minimal_room/inputs` и прогнать эталон на Linux.
