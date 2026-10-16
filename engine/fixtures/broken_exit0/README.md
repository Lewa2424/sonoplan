# Fixture: broken_exit0

Намеренно **нет** выходных файлов. Используется для проверки: `exit_code=0` + пустой workdir ⇒ `ok=false`, карта не публикуется.

```bash
cd engine/adapter
python -m sonoplan_adapter.cli validate-outputs ../fixtures/broken_exit0 \
  --manifest ../fixtures/broken_exit0/manifest.json --exit-code 0
# ожидаемый код процесса CLI: 1
```
