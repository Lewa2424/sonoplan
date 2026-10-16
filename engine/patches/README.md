# Патчи ядра (ENG-009, правило 60-engine-spps)

## Политика

- Минимальный diff; каждый `.patch` с записью: причина, до/после на fixtures, численное влияние.
- Не менять эталоны ради зелёных тестов.
- Сохранять лицензионные уведомления upstream.

## Планируемый патч: код возврата SPPS

**Факт (pinned commit `929a5c8e…`, файл `src/spps/sppsNantes.cpp`):**

```cpp
int main(int argc, char* argv[])
{
    MainProcess(argc,argv);
    // ...
    return 0;
}
```

`MainProcess` не влияет на код выхода — процесс часто завершается с `0` даже при сбое. Это подтверждает ENG-009 / S05.

**Намерение патча (ещё не применён — нет локальной сборки):**

1. Пробросить статус `MainProcess` в `return` из `main`.
2. Сохранить обёртку адаптера: даже после патча проверять наличие/размер/целостность выходов.
3. Регрессия: `fixtures/broken_exit0` + unit-тест `test_validate_outputs.py`.

Файл патча появится как `0001-spps-propagate-mainprocess-status.patch` после `git format-patch` на клоне в `.cache/isimpa`.
