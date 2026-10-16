# engine/adapter — SPPS adapter

Python-адаптер: запуск процесса SPPS, валидация выходов, заготовки декодеров.  
JSON проекта в SPPS не подаётся. **Exit code 0 ≠ успех** без валидных выходных файлов.

## Путь к бинарнику (`SPPS_BIN`)

Целевой бинарник — **Linux x86_64** из CI (см. [`docs/spps-ci-artifact.md`](../../docs/spps-ci-artifact.md)).

| Способ | Как |
|--------|-----|
| Env | `SPPS_BIN=/abs/path/to/spps` — используется, если в запросе executable = `spps` (default) |
| Явно | `SppsRunRequest(spps_executable="/abs/path/to/spps", ...)` |
| Локальный hint после `gh run download` | `engine/binaries/spps-ci/spps-linux-x86_64-929a5c8e5f59/spps` |

Checksum pinned: `engine/PINNED.json` → `binary_checksum`.

Worker на Linux/VPS должен выставлять `SPPS_BIN` (или абсолютный путь в задаче). На Windows-хосте разработчика Linux-`spps` не запускать.

## CLI (STG-04)

```powershell
cd engine\adapter
python -m sonoplan_adapter.cli check-env
python -m sonoplan_adapter.cli attempt-run ..\fixtures\minimal_room\inputs --report ..\..\ci-spps-job\attempt.json
```

Коды отказа: `SPPS_NOT_LINUX`, `SPPS_BIN_MISSING`, `FIXTURE_INPUTS_MISSING`, `SPPS_RUN_FAILED`.  
`attempt-run` exit `2` = fixture inputs missing (блокер, не фейковый success).

## Unit-тесты без бинарника

```powershell
cd engine\adapter
python -m unittest discover -s tests -v
python -m sonoplan_adapter.cli validate-outputs ..\fixtures\broken_exit0 `
  --manifest ..\fixtures\broken_exit0\manifest.json --exit-code 0
```
