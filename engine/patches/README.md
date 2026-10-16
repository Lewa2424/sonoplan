# Патчи ядра (правило 60-engine-spps)

## Политика (path A — 2026-10-16)

- **Experimental apply выключен.** `engine/scripts/apply-spps-patches.py` — no-op
  (проверка дерева + UTILISER). Файлы `*.patch` только документирующие; `git apply`
  не вызывается.
- Причина паузы: headless SPPS даёт `energySumGlobal=0`; серия deposit/link/cdt_vol
  ломала Build (redefinition marker) и не доказала energy>0. См.
  [`docs/spps-energy-blocker.md`](../../docs/spps-energy-blocker.md).
- Не изобретать dB / теплокарты из нулевой энергии.
- Не менять эталоны ради зелёных тестов.
- Сохранять лицензионные уведомления upstream.

## Documenting (не применяются)

| Файл | Было намерение | Статус |
|------|----------------|--------|
| `0001-spps-deposit-on-start-tetra.patch` | маркер в CalculationCore | **paused** — устарел / ломал Build |
| `0002-spps-link-all-tetras-within-rayon.patch` | link-all tetras в Expand | **paused** — corrupt/outdated apply |

**Pinned commit:** `929a5c8e5f590b189f29155faeff8670f3699479`

**UTILISER:** оставляем `#define` — ветка `#ifndef` не компилируется.

Включить experimental снова можно только отдельным этапом energy с до/после на
fixtures и зелёным Build — не через `SONOPLAN_APPLY_EXPERIMENTAL_SPPS_PATCHES`
(флаг сейчас отвергается скриптом).

## Планируемый патч: код возврата SPPS (ENG-009)

**Факт:** `main` в `sppsNantes.cpp` всегда `return 0` после `MainProcess`.

**Намерение:** проброс статуса + регрессия `fixtures/broken_exit0`.
