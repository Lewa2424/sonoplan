# Патчи ядра (правило 60-engine-spps)

## Политика

- Минимальный diff; каждый `.patch` с записью: причина, до/после на fixtures, численное влияние.
- Не менять эталоны ради зелёных тестов.
- Сохранять лицензионные уведомления upstream.
- **Источник истины применения:** `engine/scripts/apply-spps-patches.py` (string transforms).
  Файлы `*.patch` — документирующие; скрипт **не** вызывает `git apply` (старый
  marker в `0001` давал `redefinition of sonoplan_spps_patch` при совместном apply).

## Активные правки (`apply-spps-patches.py`, маркер `sonoplan-deposit-all-recp-v3`)

**Pinned commit:** `929a5c8e5f590b189f29155faeff8670f3699479`

**Симптом (CI):** SPPS exit 0, `.recp` / intensity / gap energy columns все 0; official
`spps/tests` control тоже 0. Бинарник pin `91839747…` содержал link-all в исходниках
сборки, но маркер вырезался linker’ом; energy всё равно 0 → одного link-all мало.

**Полярность UTILISER (не перепутать):**
- `#define UTILISER_MAILLAGE_OPTIMISATION` → компилируется ветка `#else`.
- Скомпилированный `FreeParticleTranslation` **уже всегда** вызывает deposit.
- Gate `linkedRecepteurP` — только в мёртвом `#ifndef`-overload.

**Причины нулей на punctual (при Total energy > 0):**
1. Депозит в `ParticuleFreeTranslation` шёл только по `linkedRecepteurP`.
2. `cdt_vol` мог остаться 0 при промахе `indexTetra` → `energy_sum*0`.
3. `RaySphere` возвращает false / clamp chord=0, пока частица внутри сферы
   (типично при colocated source/receiver).
4. Маркер `static const` без touch вырезался `-O2`.

**Исправления:**
1. Всегда итерировать `recepteur_p_List` при депозите.
2. Всегда задавать `cdt_vol=(c·ρ)/V_sphere`.
3. Линковать тетраэдры в `rayon+10`.
4. Robust outside RaySphere: при miss/clamp и endpoint внутри — длина шага
   (реальная энергия частицы, не фейк дБ).
5. Маркер `__attribute__((used))` + touch на **скомпилированном** `#else`-пути;
   `build-spps-native.sh` падает, если маркер отсутствует в `spps`.

**UTILISER:** оставляем `#define` — ветка `#ifndef` не компилируется.

## Планируемый патч: код возврата SPPS (ENG-009)

**Факт:** `main` в `sppsNantes.cpp` всегда `return 0` после `MainProcess`.

**Намерение:** проброс статуса + регрессия `fixtures/broken_exit0`.
