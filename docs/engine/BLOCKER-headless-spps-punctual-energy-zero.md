# BLOCKER: headless SPPS punctual energy = 0

**Статус:** PAUSED (path A) · **Дата:** 2026-10-16 · **Не изобретать dB** при `energySumGlobal == 0`.

Каноническая запись паузы: [`docs/spps-energy-blocker.md`](../spps-energy-blocker.md).

## Факт

Headless SPPS (exit 0) на CI даёт `.recp` с `energySumGlobal: 0.0` по всем punctual
приёмникам; `lpDbGlobal` остаётся `null` (`zero_energy_not_silence`). То же на
official upstream control (`spps/tests` cube), не только на SonoPlan fixture.

## Подтверждённые runs (GitHub Actions)

| Workflow | Run | SHA | Итог |
|---|---|---|---|
| Build SPPS | [38881811929](https://github.com/Lewa2424/sonoplan/actions/runs/38881811929) | `853bf2d` | **success** (последний зелёный Build до deposit-all) |
| Run SPPS Job | [38881817781](https://github.com/Lewa2424/sonoplan/actions/runs/38881817781) | `853bf2d` | failure: assert nonzero energy |
| Run SPPS Job | [38881977004](https://github.com/Lewa2424/sonoplan/actions/runs/38881977004) | `e7b0008` | failure: все receivers `energySumGlobal=0`, official `nonzero=[]` |
| Build SPPS | [38882521360](https://github.com/Lewa2424/sonoplan/actions/runs/38882521360) | `b7329d4` | **failure**: `redefinition of sonoplan_spps_patch` (git apply устаревших `.patch` + string marker) |
| Run SPPS Job | [38882521502](https://github.com/Lewa2424/sonoplan/actions/runs/38882521502) | `b7329d4` | failure (deposit-all не дал energy>0; Build уже красный) |

Артефакт `38881977004`: `result_manifest.json` — все 7 receivers fixture с
`energySumGlobal: 0.0`; `official_control/energy_raw.json` и `energy_idv0.json` —
`nonzero: []`.

## Что не доказано

Серия deposit/link/cdt_vol патчей (`b7329d4` и раньше) **не** доказала
`energySumGlobal > 0` даже на official fixture.

## Политика на паузе (path A)

- Experimental apply **выключен** (`engine/scripts/apply-spps-patches.py`).
- Build: не применять documenting `engine/patches/*.patch` через `git apply`.
- CI не требует nonzero energy для зелёного decode/honesty gate.
- UI/API не публиковать выдуманные Lp/карты из нулевой энергии.
- Новые energy-фиксы — только отдельным этапом по запросу владельца.
