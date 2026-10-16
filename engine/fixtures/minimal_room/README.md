# Fixture: minimal_room

Статус: **inputs_ready** — официальные `mesh.cbin` / `tetramesh.mbin` из pinned I-Simpa + адаптированный `config.xml`.

## Происхождение входов

| Файл | Источник (commit `929a5c8e…`) |
|------|-------------------------------|
| `inputs/mesh.cbin` | `src/python_bindings/tests/mesh.cbin` (без изменений) |
| `inputs/tetramesh.mbin` | `src/python_bindings/tests/tetramesh.mbin` (без изменений) |
| `inputs/speaker-test3.txt` | `src/spps/tests/speaker-test3.txt` (без изменений) |
| `inputs/config.xml` | Структура `src/spps/tests/config.xml`, адаптирована под этот mesh |

Адаптация config (не выдуманный mesh):

- материалы `id=100` и `id=101` (face `idMat` в официальном mesh);
- без поверхностных приёмников (`idRs=-1` в mesh);
- `workingdirectory=.`, десятичный разделитель — точка (ENG-007);
- `random_seed=1` (≠0: SetRandSeed + single-thread), `nbparticules=20000`;
- `directivite=0` (omni), `rayon_recepteurp=2`, `duree_simulation=1`, `pasdetemps=5e-4`;
- runner принудительно `LC_ALL=C` / `LC_NUMERIC=C` (atof и десятичная точка);
- расчётные полосы: 100 Hz и 1000 Hz.

Лицензия upstream: GPLv3 — см. `inputs/ORIGIN.txt` и `docs/engine-licenses.md`.

## Воспроизведение / обновление

```bash
./engine/scripts/prepare-minimal-room-fixture.sh
# или на Windows без clone:
python engine/scripts/prepare-minimal-room-fixture.py
```

## Прогон

Linux worker / GitHub Actions:

```bash
export SPPS_BIN=/path/to/spps
cd engine/adapter
python -m sonoplan_adapter.cli attempt-run ../fixtures/minimal_room/inputs \
  --required-input config.xml \
  --required-input mesh.cbin \
  --required-input tetramesh.mbin \
  --required-input speaker-test3.txt
python -m sonoplan_adapter.cli validate-outputs ../fixtures/minimal_room/inputs \
  --manifest ../fixtures/minimal_room/manifest.json --exit-code 0
```

`expected/` содержит реальные `.recp` / `statsSPPS.gabe` с успешного CI
с ненулевой энергией (обновляется после `Run SPPS Job`).
Декодер: `sonoplan_adapter.cli decode-outputs`. SCI-003 golden 0.1 dB — **pending**.
