# Лицензии расчётного ядра (LIC-001…LIC-003)

Документ фиксирует **обязанности и ссылки** для STG-01. Это не юридическое заключение и не замена полного SBOM до публичной эксплуатации (LIC-003).

## I-Simpa / SPPS — GPLv3

| Поле | Значение |
|------|----------|
| Проект | [I-Simpa](https://github.com/Universite-Gustave-Eiffel/I-Simpa) (Université Gustave Eiffel / UMRAE) |
| Лицензия | GNU General Public License **Version 3** |
| Текст в репозитории | [`LICENSE.md`](https://github.com/Universite-Gustave-Eiffel/I-Simpa/blob/main/LICENSE.md) |
| Упоминание в README | «GENERAL PUBLIC LICENSE Version 3» → GPLv3 |
| Pinned commit SonoPlan | `929a5c8e5f590b189f29155faeff8670f3699479` (см. `engine/PINNED.json`) |
| Источник ТЗ | S01, LIC-001 |

### Обязанности (кратко, не исчерпывающе)

- При распространении бинарников SPPS / модифицированного I-Simpa — предоставить Corresponding Source и текст GPLv3.
- Сохранять уведомления об авторских правах и отсутствии гарантии.
- Модификации SonoPlan в `engine/patches/` наследуются условиями применимой лицензии upstream-файлов.
- Размещение на сервере **не отменяет** обязанности GPLv3 при распространении копий; сетевые нюансы для GPLv3 отличаются от AGPL (см. TetGen ниже).

## TetGen — dual: AGPLv3-or-later **или** коммерческая лицензия WIAS

| Поле | Значение |
|------|----------|
| Компонент | TetGen (в дереве I-Simpa: `src/tetgen/`) |
| Лицензия open path | GNU Affero GPL v3 **or later** |
| Текст | [`src/tetgen/LICENSE`](https://github.com/Universite-Gustave-Eiffel/I-Simpa/blob/main/src/tetgen/LICENSE) |
| Коммерческий вариант | Запрос: tetgen@wias-berlin.de (Weierstrass Institute / WIAS) |
| Источник ТЗ | LIC-001, S08 (blob LICENSE в ТЗ: `e253c3d9…`) |

### Обязанности open-path (AGPL)

- При сетевом использовании модифицированной версии оператор должен обеспечить доступ пользователей к Corresponding Source модификаций (условие AGPL).
- Базовый путь ТЗ (LIC-002): открытая поставка с совместимой лицензией **AGPLv3-or-later** для собственного кода SonoPlan при сохранении исходных лицензий зависимостей.
- Архитектурное разделение процессов (worker ≠ UI) **не** считается автоматическим юридическим освобождением (LIC-003).

### Закрытый продукт

Если нужен проприетарный продукт — отдельно решить коммерческую лицензию TetGen и совместимость остальных частей **до** публичной эксплуатации; иначе заменить компонент и повторить численные испытания (LIC-003).

## Что ещё не закрыто

- Полный перечень зависимостей Boost / системных библиотек Linux runner / контейнера и их лицензий (SBOM) — после первой успешной сборки.
- SHA-256 бинарника SPPS в `engine/PINNED.json` (`binary_checksum`) — pinned от CI run `38867272211` (см. `docs/spps-ci-artifact.md`).
- Digest образа Docker (`image_checksum`) — только если используется optional Docker Engine на Linux; не обязателен для primary CI path.
- При распространении CI-артефакта SPPS — Corresponding Source и GPLv3 (см. выше).
- Пользовательские проекты и секреты **не** входят в публикуемый исходный код (LIC-002).

## Ссылки

- [GNU GPLv3](https://www.gnu.org/licenses/gpl-3.0.html)
- [GNU AGPLv3](https://www.gnu.org/licenses/agpl-3.0.html)
- [I-Simpa Docs / License notes](https://github.com/Universite-Gustave-Eiffel/I-Simpa/blob/main/Docs/License.txt) (Ifsttar/UGE notice)
- ТЗ: LIC-001…003, S01, S08, S25, S26
