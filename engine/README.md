# engine/ — SPPS / I-Simpa (STG-01)

Цель этапа: **доказать расчётный путь** — воспроизводимая сборка SPPS без GUI, эталонный прогон, чтение выходов, обработка «exit 0 без файлов», фиксация лицензий. Пока этап не пройден, UI не должен обещать «как будто» расчёт.

## Структура (DEV-002)

| Путь | Назначение |
|------|------------|
| `adapter/` | Python-адаптер: запуск процесса, валидация выходов, заготовки декодеров |
| `patches/` | Минимальные патчи upstream (пока план ENG-009) |
| `fixtures/` | Эталонные входы/выходы и регрессия broken_exit0 |
| `scripts/` | fetch / build (Docker + native) / run / check-env |
| `Dockerfile` | Linux-сборка SPPS в образе (`SKIPISIMPA=ON`) — optional на Linux VPS |
| `PINNED.json` | Закреплённый commit I-Simpa + статус сборки |
| `../.github/workflows/build-spps.yml` | **Primary:** CI-сборка на Linux runner |
| `../docs/engine-build-without-docker.md` | CI / remote VPS / оценка Windows native |

## Pinned I-Simpa

- **Commit:** `929a5c8e5f590b189f29155faeff8670f3699479`
- **Проверен:** 2026-10-16 через GitHub API (`commits/main` на эту дату)
- **Репозиторий:** https://github.com/Universite-Gustave-Eiffel/I-Simpa

Ссылка только на ветку `main` недостаточна (ENG-001) — используйте SHA из `PINNED.json`.

## Воспроизводимая сборка (primary = без Docker Desktop)

На машине разработчика (Windows 10.0.19044) **Docker Desktop blocked** — обновление ОС недоступно. Primary path:

1. **GitHub Actions** — workflow `Build SPPS` (см. `.github/workflows/build-spps.yml`).
2. **Удалённый Linux VPS/VM** — те же команды:

```bash
chmod +x engine/scripts/fetch-isimpa.sh engine/scripts/build-spps-native.sh
./engine/scripts/build-spps-native.sh
# → engine/dist/spps + SHA256SUMS + archive
```

Подробности: [`docs/engine-build-without-docker.md`](../docs/engine-build-without-docker.md).

### Optional: Docker Engine на Linux (не Desktop на Windows)

```bash
cd engine
./scripts/build-spps.sh
```

Эквивалент вручную:

```bash
docker build \
  --build-arg ISIMPA_COMMIT=929a5c8e5f590b189f29155faeff8670f3699479 \
  -t sonoplan-spps:929a5c8e5f59 \
  -f Dockerfile .
```

CMake: `-DSKIPISIMPA=ON` (без GUI). **Не** путать с `-DLIBSIMPA_ONLY=ON` — это не сборка SPPS (ENG-002).

После успеха: записать SHA-256 бинарника в `PINNED.json` → `binary_checksum` (и digest образа → `image_checksum`, если собирали Docker на Linux).

### Native Windows MSVC/MinGW

**Не целевой путь** для STG-01 (другой ABI, GUI-ориентированный upstream Windows CI, нет совпадения с pin toolchain Ubuntu 22.04). См. раздел C в `docs/engine-build-without-docker.md`.

## Прогон эталона

```bash
./scripts/run-spps-fixture.sh   # Linux-хост с бинарником; требует config.xml + mesh в fixtures/minimal_room/inputs
```

Сейчас inputs пусты — бинарники не выдуманы.

## Адаптер (локально без SPPS)

```powershell
cd engine\adapter
python -m unittest tests/test_validate_outputs.py
python -m sonoplan_adapter.cli validate-outputs ..\fixtures\broken_exit0 `
  --manifest ..\fixtures\broken_exit0\manifest.json --exit-code 0
```

Инвариант: **exit code 0 ≠ успех** без валидных выходов (ENG-009).

STG-02+ (web/API) на Windows продолжается **без** локального SPPS.

## Лицензии

См. [`docs/engine-licenses.md`](../docs/engine-licenses.md): I-Simpa GPLv3, TetGen AGPLv3-or-later / commercial WIAS.

## Статус хоста (2026-10-16)

Проверено на машине разработки (см. также `BUILD_STATUS.md`):

- Docker Desktop: **blocked** (ОС 19044, обновление недоступно)
- WSL: ядро/сообщение об обновлении; **рабочий Linux-дистрибутив для сборки не готов**
- Primary path: **GitHub Actions / remote Linux** (не локальный Docker Desktop)
- Локальный `git clone` I-Simpa в workspace: **заблокирован** Cursor Hooks; pin SHA взят из GitHub API; clone — в CI/VPS или внутри `Dockerfile` на Linux
- Сборка SPPS и прогон эталона: **не выполнены** (нет Linux runner / артефакта)
- Unit-тесты валидации выходов адаптера: **4/4 OK** без Docker

Следующий шаг: git remote → GitHub Actions `Build SPPS` (или Ubuntu VPS + `build-spps-native.sh`) → artifact → `binary_checksum` в `PINNED.json` → fixtures inputs → прогон на Linux.
