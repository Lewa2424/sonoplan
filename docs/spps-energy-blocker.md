# SPPS punctual energy blocker

**Статус:** CLOSED · **Дата:** 2026-10-16  
Критерий снят: Build + Run SPPS Job + Official Smoke с `energySumGlobal > 0` и конечным `lpDb`.

## Факт (исторический)

Headless SPPS на Linux CI (exit 0) писал punctual `.recp` с **`energySumGlobal = 0`**.
Адаптер корректно оставлял `lpDbGlobal = null` (`zero_energy_not_silence`).

## Корневая причина

1. UTILISER `FreeParticleTranslation` гейтил депозит по `linkedRecepteurP`.
2. `RaySphere` давал miss / chord=0, пока частица уже внутри сферы приёмника.
3. `cdt_vol` мог остаться 0.

## Исправление (в `main`, pin `ba80c40` / Build 38887792132)

`engine/scripts/apply-spps-patches.py`: deposit-all, `cdt_vol`, robust chord
вне `RaySphere`, marker на живом `#else` UTILISER.

## Подтверждение

| Workflow | Run | Итог |
|---|---|---|
| Run SPPS Job | [38888407006](https://github.com/Lewa2424/sonoplan/actions/runs/38888407006) | success, `r_near` ≈ 82.8 dB |
| Official Smoke | [38888386969](https://github.com/Lewa2424/sonoplan/actions/runs/38888386969) | success |

Эталонные `.recp` лежат в `engine/fixtures/minimal_room/expected/`.
