# Сборка SPPS без Docker Desktop (STG-01)

**Контекст владельца:** на Windows 10.0.19044 Docker Desktop недоступен (обновление ОС невозможно). Локальный MVP UI/API (STG-02+) продолжается без Docker.

## Primary path

| Приоритет | Путь | Когда |
|-----------|------|--------|
| **1 (primary)** | GitHub Actions: `.github/workflows/build-spps.yml` | Есть git remote на GitHub |
| **2** | Удалённый Linux VPS/VM (те же команды, что CI) | Нет GitHub Actions или нужен свой runner |
| **3 (optional)** | Docker Engine **на Linux VPS** (`./scripts/build-spps.sh`) | Удобно для воспроизводимого образа |
| **не целевой** | Native Windows MSVC / MinGW | См. ниже |

Локальный Docker Desktop на машине разработчика: **blocked** — не primary path.

## A) GitHub Actions

1. Создать репозиторий на GitHub и добавить remote (сейчас в workspace git remote может отсутствовать).
2. Запушить ветку с `engine/` и `.github/workflows/build-spps.yml`.
3. Actions → **Build SPPS** → **Run workflow** (`workflow_dispatch`), либо push в пути `engine/**` / workflow-файл.
4. Скачать artifact `spps-linux-x86_64-<12 hex>`: `spps`, `ORIGIN.txt`, `SHA256SUMS`, `.tar.gz`.
5. Записать SHA-256 из `SHA256SUMS` в `engine/PINNED.json` → `binary_checksum` после проверки.
6. (Опционально) положить бинарник на Linux-хост worker’а; Windows-хост UI/API бинарник для расчёта не запускает.

Workflow на runner `ubuntu-22.04`: clone pinned I-Simpa → `cmake -DSKIPISIMPA=ON` → artifact. Не путать с `-DLIBSIMPA_ONLY=ON` (ENG-002).

## B) Удалённый Linux VPS / VM

Требования: Ubuntu 22.04 (или совместимый), сеть к GitHub, ~4+ GiB RAM, build-essential.

```bash
# 1) Зависимости (как в CI / Dockerfile; GUI-пакеты не нужны при SKIPISIMPA=ON)
sudo apt-get update
sudo apt-get install -y --no-install-recommends \
  build-essential ca-certificates cmake git python3 python3-dev swig \
  libboost-all-dev byacc gettext libpng-dev libjpeg-dev

# 2) Клон SonoPlan (после появления remote) или копирование дерева engine/
git clone <YOUR_SONOPLAN_REMOTE> sonoplan
cd sonoplan

# 3) Та же команда, что CI
chmod +x engine/scripts/fetch-isimpa.sh engine/scripts/build-spps-native.sh
./engine/scripts/build-spps-native.sh
# → engine/dist/spps , SHA256SUMS , spps-linux-x86_64-*.tar.gz
```

### Опция: Docker Engine на Linux VPS (не Desktop)

Если на VPS установлен Docker Engine:

```bash
cd engine
./scripts/build-spps.sh
```

Это **не** требует Docker Desktop на Windows-машине разработчика.

## C) Native Windows (MSVC / MinGW) — не целевой путь

| Фактор | Оценка |
|--------|--------|
| Upstream toolchain для SonoPlan pin | Linux `ubuntu:22.04` / g++ (см. `PINNED.json`) |
| I-Simpa Windows CI | Есть, но ориентирован на полный GUI-стек (wxWidgets и др.) |
| `SKIPISIMPA=ON` на MSVC | Теоретически возможен, на практике Boost/SWIG/Python/CPM и пути install расходятся с Linux-эталоном |
| Воспроизводимость checksum | Другой ABI → другой бинарник; эталоны и worker рассчитаны на Linux SPPS |
| Windows 19044 + отсутствие нормального WSL-дистрибутива | Усугубляет локальную native-сборку |

**Вердикт: не целевой путь для STG-01.** Не блокировать MVP UI/API ожиданием MSVC-сборки. Binary artifact берём с Linux CI/VPS.

## После первого артефакта

1. Заполнить `binary_checksum` (и при docker-на-VPS — `image_checksum`) в `PINNED.json`.
2. Положить реальные mesh/XML в `engine/fixtures/minimal_room/inputs`.
3. Прогон `./scripts/run-spps-fixture.sh` на Linux-хосте с бинарником.
4. STG-02+ на Windows продолжается независимо (API/web без SPPS).

## Связанные файлы

- `engine/scripts/build-spps-native.sh` — native Linux
- `engine/scripts/build-spps.sh` — Docker (optional на Linux)
- `.github/workflows/build-spps.yml` — CI
- `engine/BUILD_STATUS.md` — статус хоста разработчика
- `docs/engine-licenses.md` — GPLv3 / TetGen
