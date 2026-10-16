# inputs/

Реальные входы SPPS для STG-01 (не scaffold):

| Файл | Роль |
|------|------|
| `config.xml` | Адаптированный XML (точка как разделитель; materials 100/101) |
| `mesh.cbin` | Официальный surface mesh из I-Simpa `python_bindings/tests` |
| `tetramesh.mbin` | Официальный tetra mesh из того же каталога |
| `speaker-test3.txt` | Директивность источника из `spps/tests` |
| `ORIGIN.txt` | Provenance / GPLv3 notice |
| `SHA256SUMS` | Контрольные суммы входов |

Пересборка: `engine/scripts/prepare-minimal-room-fixture.sh` (или `.py`).
