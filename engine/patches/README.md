# Патчи ядра (правило 60-engine-spps)

## Политика

- Минимальный diff; каждый `.patch` с записью: причина, до/после на fixtures, численное влияние.
- Не менять эталоны ради зелёных тестов.
- Сохранять лицензионные уведомления upstream.
- Применение: `engine/scripts/apply-spps-patches.py` из `build-spps-native.sh` (`git apply` + string fallback).

## `0001-spps-deposit-on-start-tetra.patch`

**Pinned commit:** `929a5c8e5f590b189f29155faeff8670f3699479`  
**Файл:** `src/spps/CalculationCore.cpp` — `FreeParticleTranslation` (ветка `UTILISER_MAILLAGE_OPTIMISATION`).

**Симптом (CI minimal_room):** SPPS exit 0, частицы поглощаются материалами (~20k), все punctual `.recp` с `energy_sum=0`.

**Причина:** upstream сначала навигирует в *конечный* тетраэдр шага, затем вызывает `ParticuleFreeTranslation` только если у *конечного* тетраэдра есть `linkedRecepteurP`. Частица, покидающая linked-тетраэдр за один timestep, не депозитит энергию.

**Исправление:** депозит по linked receivers *стартового* тетраэдра до навигации (как в ветке без UTILISER). Навигация `currentTetra` сохраняется.

**Влияние:** ненулевая энергия / конечный `lpDb` на punctual receivers при том же fixture; численные значения — честный SPPS, не подделка дБ.

## Планируемый патч: код возврата SPPS (ENG-009)

**Факт:** `main` в `sppsNantes.cpp` всегда `return 0` после `MainProcess` — процесс может завершиться с 0 при сбое.

**Намерение (ещё не в tree как рабочий патч):** проброс статуса `MainProcess` + регрессия `fixtures/broken_exit0`.
