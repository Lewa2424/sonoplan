# Патчи ядра (правило 60-engine-spps)

## Политика

- Минимальный diff; каждый `.patch` с записью: причина, до/после на fixtures, численное влияние.
- Не менять эталоны ради зелёных тестов.
- Сохранять лицензионные уведомления upstream.
- Применение: `engine/scripts/apply-spps-patches.py` из `build-spps-native.sh`.
- **Запрещено** снимать `#define UTILISER_MAILLAGE_OPTIMISATION`: ветка `#ifndef` в `CalculationCore.cpp` не компилируется (`doInvertNormal` / `percCollision`).

## Pinned commit

`929a5c8e5f590b189f29155faeff8670f3699479`

## `0001-spps-deposit-on-start-tetra.patch` (marker only)

**Файл:** `src/spps/CalculationCore.cpp`  
**Содержание:** `.rodata` маркер `sonoplan-link-all-tetras-v1` для проверки, что CI-артефакт собран с патчами.  
**Не делает:** rewrite `FreeParticleTranslation` / отключение UTILISER (раньше ломало сборку).

Старое имя файла сохранено для совместимости путей; смысл — marker, не deposit.

## `0002-spps-link-all-tetras-within-rayon.patch`

**Файл:** `src/spps/sppsInitialisation.cpp` — `ExpandPunctualReceiverTetrahedronLocalisation`.

**Симптом:** CI minimal_room / official cube: SPPS exit 0, `Particles remaining ≈ Total`, punctual `.recp` `energy_sum=0`.

**Причина:** upstream `RecursiveTetraTest` стартует только с *соседей* содержащего тетраэдра; на 6-тетраэдрном cube связь приёмник↔тетра неполная для депозита.

**Исправление:** после upstream expand дополнительно линкуем каждый тетраэдр, чей центроид в пределах `rayon+10` м.

**Влияние (ожидаемое):** ненулевая энергия на punctual receivers при пролёте частиц. Если после зелёной сборки energy всё ещё 0 — корень не в apply патчей, а в запуске/физике/материалах mesh; не invent dB.

## Планируемый патч: код возврата SPPS (ENG-009)

**Факт:** `main` в `sppsNantes.cpp` всегда `return 0` после `MainProcess`.  
**Намерение:** проброс статуса + регрессия `fixtures/broken_exit0`.
