# Fixture: minimal_room

Статус: **inputs_ready** — официальный куб I-Simpa `cube.cbin` / `cube_mesh.mbin` + адаптированный `config.xml`.

## Происхождение входов

| Файл | Источник (commit `929a5c8e…`) |
|------|-------------------------------|
| `inputs/mesh.cbin` | `src/lib_interface/tests/cube.cbin` (5×5×5 m, idMat=0) |
| `inputs/tetramesh.mbin` | `src/lib_interface/tests/cube_mesh.mbin` |
| `inputs/speaker-test3.txt` | `src/spps/tests/speaker-test3.txt` |
| `inputs/config.xml` | Структура `src/spps/tests/config.xml`, адаптирована под куб |

Адаптация config:

- материал `id=0` (face `idMat` в `cube.cbin`);
- без поверхностных приёмников (`idRs=-1`);
- `workingdirectory=./`, десятичный разделитель — точка (ENG-007);
- `random_seed=1` (≠0: SetRandSeed + single-thread), `nbparticules=20000`;
- `directivite=0` (omni), `rayon_recepteurp=1`, `computation_method=1` (UTILISER), `r_near` colocated with source, `duree_simulation=0.5`, `pasdetemps=5e-4`;
- runner принудительно `LC_ALL=C` / `LC_NUMERIC=C`;
- расчётные полосы: 100 Hz и 1000 Hz.

**Не** использовать `python_bindings/tests/mesh.cbin` (20×30×10) с этим кластером приёмников — в CI энергия punctual оставалась 0 при ненулевых ударах о стены.

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
