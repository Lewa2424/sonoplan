# BLOCKER: headless SPPS punctual energy = 0

**Статус:** открыт · **Дата:** 2026-10-16 · **Не изобретать dB** при `energySumGlobal == 0`.

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
`energySumGlobal > 0` даже на official fixture. Root-cause agent `41e4aecc`:
выводов в `docs/commits/` нет (каталог пуст на момент записи).

## Политика до снятия BLOCKER

- Не делать слепой deposit-патч без доказанной гипотезы и воспроизводимого до/после.
- Build: не применять устаревшие documenting `engine/patches/*.patch` через
  `git apply` вместе со string-path (ломает компиляцию маркером).
- UI/API не публиковать выдуманные Lp/карты из нулевой энергии.
