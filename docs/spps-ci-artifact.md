# SPPS CI artifact (Linux x86_64)

Pinned build from GitHub Actions — **не коммитить** бинарник в git (см. `engine/binaries/` в `.gitignore`). Checksum — в `engine/PINNED.json` → `binary_checksum`.

## Закреплённый run

| Поле | Значение |
|------|----------|
| Run | [38878095021](https://github.com/Lewa2424/sonoplan/actions/runs/38878095021) |
| Repo | `Lewa2424/sonoplan` |
| Artifact | `spps-linux-x86_64-929a5c8e5f59` |
| I-Simpa commit | `929a5c8e5f590b189f29155faeff8670f3699479` |
| SHA-256 (`spps`) | `c5e30a7b1647ed73b26aae58815914a55cc1785223f954ba7e12b3eda0234eb5` |
| Дата pin | 2026-10-16 |
| Примечание | Pin после `0d63e1b` (deposit-on-start-tetra). SHA совпал с предыдущим артефактом — критерий приёмки: `energySumGlobal > 0` в Run SPPS Job. |

## Скачать (gh CLI)

```bash
# из корня репозитория SonoPlan
gh run download 38878095021 --repo Lewa2424/sonoplan -D engine/binaries/spps-ci/
```

Локальный путь к бинарнику после download:

`engine/binaries/spps-ci/spps-linux-x86_64-929a5c8e5f59/spps`

Проверка checksum (PowerShell):

```powershell
(Get-FileHash engine\binaries\spps-ci\spps-linux-x86_64-929a5c8e5f59\spps -Algorithm SHA256).Hash.ToLower()
# ожидается: c5e30a7b1647ed73b26aae58815914a55cc1785223f954ba7e12b3eda0234eb5
```

Linux:

```bash
sha256sum engine/binaries/spps-ci/spps-linux-x86_64-929a5c8e5f59/spps
# или сравнить с engine/.../SHA256SUMS из артефакта
```

## Содержимое artifact (run 38878095021)

| Файл | Размер (байт) |
|------|----------------|
| `spps` | 1 119 800 |
| `spps-linux-x86_64-929a5c8e5f59.tar.gz` | 435 465 |
| `ORIGIN.txt` | 160 |
| `SHA256SUMS` | 71 |

## Worker / адаптер

На **Linux** CI/VPS:

```bash
export SPPS_BIN=/absolute/path/to/spps
# адаптер: SppsRunRequest(spps_executable=...) или default «spps» → читает SPPS_BIN
```

На **Windows**-хосте разработчика Linux-бинарник **не запускать** (другой ABI). UI/API на Windows — без локального SPPS; расчёт — на Linux worker.

Подробности сборки: [`engine-build-without-docker.md`](engine-build-without-docker.md). Адаптер: [`../engine/adapter/README.md`](../engine/adapter/README.md).
