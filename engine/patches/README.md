# Патчи ядра (правило 60-engine-spps)

## Политика

- Минимальный diff; каждый `.patch` с записью: причина, до/после на fixtures, численное влияние.
- Не менять эталоны ради зелёных тестов.
- Сохранять лицензионные уведомления upstream.
- Применение: `engine/scripts/apply-spps-patches.py` из `build-spps-native.sh` (`git apply` + string fallback).

## Активные правки (`apply-spps-patches.py`)

**Pinned commit:** `929a5c8e5f590b189f29155faeff8670f3699479`

**Симптом (CI minimal_room):** SPPS exit 0, материалы поглощают ~20k частиц, все punctual `.recp` с `energy_sum=0`.

**Причины:**
1. `UTILISER_MAILLAGE_OPTIMISATION`: депозит только если у *конечного* тетраэдра шага есть `linkedRecepteurP`.
2. На 6-тетраэдрном cube `ExpandPunctualReceiver…` / `RecursiveTetraTest` оставляли часть объёма без связи с приёмником.

**Исправления (маркер `sonoplan-deposit-start-tetra-v2` обязан быть в бинарнике):**
1. Отключить `#define UTILISER_MAILLAGE_OPTIMISATION` в `sppsTypes.h` (ветка без UTILISER всегда вызывает `ParticuleFreeTranslation`).
2. Переписать UTILISER-`FreeParticleTranslation` на депозит со *стартового* тетраэдра (на будущее).
3. Дополнительно линковать все тетраэдры вблизи сферы приёмника в `ExpandPunctualReceiverTetrahedronLocalisation`.

**Влияние:** ненулевая энергия / конечный `lpDb` на punctual receivers; дБ не подделываются.

Документирующий `.patch`: `0001-spps-deposit-on-start-tetra.patch` (string fallback — источник истины в `apply-spps-patches.py`).

## `0002-spps-link-all-tetras-within-rayon.patch`

**Pinned commit:** `929a5c8e5f590b189f29155faeff8670f3699479`  
**Файл:** `src/spps/sppsInitialisation.cpp` — `ExpandPunctualReceiverTetrahedronLocalisation`.

**Симптом:** после колокации `r_near` с источником CI всё ещё даёт `ABS_SURF≈20k` и `energy_sum=0` на всех punctual `.recp`.

**Причина:** upstream `RecursiveTetraTest` не гарантирует `linkedRecepteurP` на стартовом тетраэдре частицы для 6-тетраэдрного cube smoke.

**Исправление:** после upstream expand дополнительно линкуем каждый тетраэдр, чей центроид в пределах `rayon+10` м от приёмника.

## Планируемый патч: код возврата SPPS (ENG-009)

**Факт:** `main` в `sppsNantes.cpp` всегда `return 0` после `MainProcess` — процесс может завершиться с 0 при сбое.

**Намерение (ещё не в tree как рабочий патч):** проброс статуса `MainProcess` + регрессия `fixtures/broken_exit0`.
