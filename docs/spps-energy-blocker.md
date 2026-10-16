# SPPS punctual energy blocker (пауза)

**Статус:** PAUSED (path A) · **Дата:** 2026-10-16  
**Решение владельца:** не гнаться за punctual energy/дБ сейчас; дожимать UI + Neon.

## Факт

Headless SPPS на Linux CI (exit 0) пишет punctual `.recp` с **`energySumGlobal = 0`**
по приёмникам. Адаптер корректно оставляет `lpDbGlobal = null`
(`zero_energy_not_silence`) — **не** «0 дБ / тишина». То же на official I-Simpa
control (`spps/tests`), не только на SonoPlan `minimal_room`.

Теплокарта / surface map из punctual не публикуется (`mapAvailable=false`).

## Подтверждённые runs

| Workflow | Run | Итог |
|----------|-----|------|
| Build SPPS | [38881811929](https://github.com/Lewa2424/sonoplan/actions/runs/38881811929) | success (до deposit-all) |
| Run SPPS Job | [38881817781](https://github.com/Lewa2424/sonoplan/actions/runs/38881817781) | failure: assert nonzero energy |
| Run SPPS Job | [38881977004](https://github.com/Lewa2424/sonoplan/actions/runs/38881977004) | все receivers energy=0 |
| Build SPPS | [38882521360](https://github.com/Lewa2424/sonoplan/actions/runs/38882521360) | failure: `redefinition of sonoplan_spps_patch` |
| Pin artifact | [38879414939](https://github.com/Lewa2424/sonoplan/actions/runs/38879414939) | known-good Build checksum в `PINNED.json` |

Подробнее: [`docs/engine/BLOCKER-headless-spps-punctual-energy-zero.md`](engine/BLOCKER-headless-spps-punctual-energy-zero.md).

## Что сделано на паузе

- Experimental SonoPlan patches **не применяются** (`apply-spps-patches.py` no-op).
- Build SPPS не требует patch marker в бинарнике.
- CI `Run SPPS Job` / official smoke: decode + honesty (`lpDb=null` при energy=0);
  **не** fail на «ждём nonzero energy».
- UI «Расчёты»: явный текст, что акустические уровни не подтверждены; без теплокарты
  и без фейковых чисел.

## Отдельный этап (позже)

Снятие blocker только после воспроизводимого `energySumGlobal > 0` на headless
(official control и/или fixture) с зелёным Build и записью до/после. До этого —
никаких новых energy-фиксов в основной ветке без явного запроса владельца.
