# Fixture: minimal_room

Статус: **scaffold** — нет бинарных `mesh.cbin` / `tetramesh.mbin` и нет golden-результатов, пока SPPS не собран и не прогнан.

## План заполнения (после Docker-сборки)

1. Собрать образ: `engine/scripts/build-spps.sh`
2. Подготовить геометрию через `preprocess` + TetGen из того же pinned commit (или экспортировать эталон из I-Simpa).
3. Положить в `inputs/`: `config.xml`, `mesh.cbin`, `tetramesh.mbin`
4. Прогнать SPPS с `random_seed=0` и Debug/без внутренней MT для воспроизводимости (CAL-005).
5. Сохранить эталонные выходы в `expected/` с checksums; обновить `golden_values` в `manifest.json`.
6. Не подменять карту заранее нарисованным изображением.

## Контракт имён

Имена файлов согласованы с upstream `src/spps/tests/config.xml` на pinned commit. Локаль XML в адаптере — UTF-8 + точка как десятичный разделитель (ENG-007); upstream-примеры с запятой не копировать вслепую.
