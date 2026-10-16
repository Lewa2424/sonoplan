# expected/

Реальные выходы SPPS с успешного CI `Run SPPS Job`
([38888407006](https://github.com/Lewa2424/sonoplan/actions/runs/38888407006), pin Build 38887792132).
**Не** выдуманные дБ.

| Файл | Назначение |
|------|------------|
| `Punctual receivers/*/Sound level.recp` | Эталон GABE/.recp + Windows MVP fixture_replay |
| `statsSPPS.gabe` | Статистика частиц |
| `result_manifest.ci.json` | Манифест того же прогона (справочно) |
| `ORIGIN.txt` | Происхождение артефакта |

На Windows API без Linux SPPS декодирует эти файлы (`executionMode=fixture_replay`) —
честно помечает, что это не локальный прогон сетки пользователя.
Теплокарта поверхности по-прежнему не публикуется из punctual.
