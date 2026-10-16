# Патчи ядра (правило 60-engine-spps)

## Политика

- Минимальный diff; каждый `.patch` с записью: причина, до/после на fixtures, численное влияние.
- Не менять эталоны ради зелёных тестов.
- Сохранять лицензионные уведомления upstream.
- **Источник истины применения:** `engine/scripts/apply-spps-patches.py` (string fallback).
  Файлы `*.patch` — документирующие; `git apply` может падать, fallback обязателен.

## Активные правки (`apply-spps-patches.py`, маркер `sonoplan-deposit-all-recp-v3`)

**Pinned commit:** `929a5c8e5f590b189f29155faeff8670f3699479`

**Симптом (CI):** SPPS exit 0, `.recp` / intensity / gap energy columns все 0; official
`spps/tests` control тоже 0. Бинарник pin `91839747…` содержал link-all в исходниках
сборки, но маркер вырезался linker’ом; energy всё равно 0 → одного link-all мало.

**Причины:**
1. Депозит в `ParticuleFreeTranslation` шёл только по `linkedRecepteurP` (оптимизация
   UTILISER) — на smoke-mesh связи могут быть неполными.
2. `cdt_vol` выставлялся только при валидном `indexTetra` в Expand; при промахе
   Init → `cdt_vol=0` → запись `energy_sum*cdt_vol` даёт нули даже при ненулевом
   накоплении.
3. Маркер `static const` без использования вырезался `-O2` / gc-sections → ложное
   ощущение «патч в бинарнике».

**Исправления:**
1. Всегда итерировать `recepteur_p_List` при депозите (link — опционально).
2. Всегда задавать `cdt_vol=(c·ρ)/V_sphere` для каждого punctual receiver.
3. Дополнительно линковать тетраэдры в `rayon+10`.
4. Маркер `__attribute__((used))` + вызов из UTILISER `FreeParticleTranslation`;
   `build-spps-native.sh` **падает**, если `grep -a` не находит маркер в `spps`.

**UTILISER:** оставляем `#define` — ветка `#ifndef` не компилируется.

## Планируемый патч: код возврата SPPS (ENG-009)

**Факт:** `main` в `sppsNantes.cpp` всегда `return 0` после `MainProcess`.

**Намерение:** проброс статуса + регрессия `fixtures/broken_exit0`.
