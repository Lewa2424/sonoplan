# SPPS punctual energy blocker

**Статус:** IN PROGRESS (ungate UTILISER deposit) · **Дата:** 2026-10-16  
Пауза path A снимается: владелец запросил честный ненулевой эталонный прогон.

## Факт

Headless SPPS на Linux CI (exit 0) писал punctual `.recp` с **`energySumGlobal = 0`**.
Адаптер корректно оставлял `lpDbGlobal = null` (`zero_energy_not_silence`) —
**не** «0 дБ / тишина». То же на official I-Simpa control, не только на
`minimal_room`.

## Корневая причина (подтверждена кодом)

Под `#define UTILISER_MAILLAGE_OPTIMISATION` функция
`CalculationCore::FreeParticleTranslation` вызывала
`ReportManager::ParticuleFreeTranslation` **только если**
`currentTetra->linkedRecepteurP != nullptr`. На 6-тетраэдрном smoke-mesh связи
неполны → депозит не вызывался → `energy_sum` остаётся 0. Дополнительно
`cdt_vol` мог остаться 0 при промахе `indexTetra` → запись
`energy_sum * cdt_vol` обнуляла бы даже накопленную энергию.

## Исправление

`engine/scripts/apply-spps-patches.py` (маркер `sonoplan-deposit-all-recp-v3`):

1. always `cdt_vol`;
2. link-all `rayon+10`;
3. deposit по всему `recepteur_p_List`;
4. **ungate** UTILISER FreeParticleTranslation;
5. used-marker в бинарнике (fail build если нет).

CI `Run SPPS Job` снова требует `energySumGlobal > 0` и конечный `lpDb`
хотя бы на одном receiver (без фейковых дБ).

## Критерий снятия blocker

Зелёный Build SPPS + Run SPPS Job с `energySumGlobal > 0`, конечным `lpDb`,
обновлённым `engine/PINNED.json`.
