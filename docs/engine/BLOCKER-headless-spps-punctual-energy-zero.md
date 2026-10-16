# BLOCKER: headless SPPS punctual energy = 0

**Статус:** FIX IN FLIGHT · **Дата:** 2026-10-16 · **Не изобретать dB** при `energySumGlobal == 0`.

Каноническая запись: [`docs/spps-energy-blocker.md`](../spps-energy-blocker.md).

## Факт

Headless SPPS (exit 0) на CI давал `.recp` с `energySumGlobal: 0.0` по всем punctual
приёмникам; `lpDbGlobal` оставался `null`. То же на official upstream control.

## Корневая причина

UTILISER `FreeParticleTranslation` гейтил вызов депозита по
`linkedRecepteurP` на end-tetra; на smoke-mesh депозит не вызывался.
Плюс `cdt_vol` мог быть 0.

## Исправление

См. `engine/scripts/apply-spps-patches.py` — deposit-all + cdt_vol +
**utiliser-ungate** + used marker `sonoplan-deposit-all-recp-v3`.

## Подтверждённые runs (до фикса)

| Workflow | Run | SHA | Итог |
|---|---|---|---|
| Run SPPS Job | [38881817781](https://github.com/Lewa2424/sonoplan/actions/runs/38881817781) | `853bf2d` | failure: assert nonzero energy |
| Run SPPS Job | [38881977004](https://github.com/Lewa2424/sonoplan/actions/runs/38881977004) | `e7b0008` | все receivers energy=0 |
| Build SPPS | [38882521360](https://github.com/Lewa2424/sonoplan/actions/runs/38882521360) | `b7329d4` | failure: marker redefinition |
