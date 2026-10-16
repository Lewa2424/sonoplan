# SPPS CI artifact (Linux x86_64)

Pinned build from GitHub Actions — **не коммитить** бинарник в git (см. `engine/binaries/` в `.gitignore`). Checksum — в `engine/PINNED.json` → `binary_checksum`.

## Закреплённый run

| Поле | Значение |
|------|----------|
| Run | [38879414939](https://github.com/Lewa2424/sonoplan/actions/runs/38879414939) |
| Repo | `Lewa2424/sonoplan` |
| Artifact | `spps-linux-x86_64-929a5c8e5f59` |
| I-Simpa commit | `929a5c8e5f590b189f29155faeff8670f3699479` |
| SHA-256 (`spps`) | `918397477af40d73e6ee96ff7748db1a705b6df6d1ede13ec85d0043f2c42d16` |
| Дата pin | 2026-10-16 |
| Примечание | Known-good pin. Experimental patches paused (path A). Energy=0 на headless — blocker, не критерий зелёного CI; см. `docs/spps-energy-blocker.md`. |

## Скачать (gh CLI)

```bash
# из корня репозитория SonoPlan
gh run download 38879414939 --repo Lewa2424/sonoplan -D engine/binaries/spps-ci/
```

Локальный путь к бинарнику после download:

`engine/binaries/spps-ci/spps-linux-x86_64-929a5c8e5f59/spps`

Проверка checksum (PowerShell):

```powershell
(Get-FileHash engine\binaries\spps-ci\spps-linux-x86_64-929a5c8e5f59\spps -Algorithm SHA256).Hash.ToLower()
# ожидается: 918397477af40d73e6ee96ff7748db1a705b6df6d1ede13ec85d0043f2c42d16
```

Linux:

```bash
sha256sum engine/binaries/spps-ci/spps-linux-x86_64-929a5c8e5f59/spps
# или сравнить с engine/.../SHA256SUMS из артефакта
```

## Содержимое artifact (run 38879414939)

| Файл | Размер (байт) |
|------|----------------|
| `spps` | (см. artifact) |
| `spps-linux-x86_64-929a5c8e5f59.tar.gz` | (см. artifact) |
| `ORIGIN.txt` | (см. artifact) |
| `SHA256SUMS` | `918397477af40d73e6ee96ff7748db1a705b6df6d1ede13ec85d0043f2c42d16  spps` |

## Worker / адаптер

На **Linux** CI/VPS:

```bash
export SPPS_BIN=/absolute/path/to/spps
# адаптер: SppsRunRequest(spps_executable=...) или default «spps» → читает SPPS_BIN
```

На **Windows**-хосте разработчика Linux-бинарник **не запускать** (другой ABI). UI/API на Windows — без локального SPPS; расчёт — на Linux worker.

Подробности сборки: [`engine-build-without-docker.md`](engine-build-without-docker.md). Адаптер: [`../engine/adapter/README.md`](../engine/adapter/README.md).
