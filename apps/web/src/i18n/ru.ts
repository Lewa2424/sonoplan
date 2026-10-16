/** Пользовательские строки UI (старт: русский через словари). */
export const ru = {
  appName: "SonoPlan",
  nav: {
    projects: "Проекты",
    model: "Модель",
    calculations: "Расчёты",
  },
  projects: {
    title: "Проекты",
    empty: "Проектов пока нет.",
    hint: "Создание идёт через API на localhost:8000. Без API — локальный черновик (offline).",
    create: "Создать проект",
    namePlaceholder: "Название цеха",
    open: "Открыть",
    offline: "Локальный черновик (offline)",
    offlineBadge: "offline / mock UI",
    loading: "Загрузка…",
    apiError: "Нет связи с API",
    apiOk: "API доступен",
  },
  model: {
    title: "Модель",
    empty: "Сначала откройте или создайте проект.",
    hint: "План сверху (X,Y). Высота — Z вверх. Без фейковой карты уровней.",
    noProject: "Проект не выбран — перейдите в «Проекты».",
    viewTop: "Сверху",
    todo3d: "3D-вид (коробка комнаты) — TODO STG-03+/CODE_MAP",
  },
  calculations: {
    title: "Расчёты",
    empty: "Очередь расчётов недоступна.",
    lead: "Задание привязано к ревизии и snapshotHash. Тепловая карта не подставляется.",
    levelsReady:
      "Punctual уровни (Lp, дБ) из реального SPPS .recp. Нулевая энергия ≠ 0 дБ.",
    levelsReplay:
      "Windows MVP: уровни с эталонного CI-прогона (fixture_replay), не локальный SPPS по вашей сетке. Карта поверхности — позже.",
    levelsActions:
      "Linux SPPS через GitHub Actions (бесплатный worker). Phase 1: сетка всё ещё fixture minimal_room, не экспорт вашей геометрии. Карта — позже.",
    levelsPending:
      "Расчёт в очереди GitHub Actions… Обновление при опросе статуса (обычно несколько минут).",
    levelsIdle:
      "Ревизия готова. Запустите расчёт — до job нет Lp (это не «тишина»).",
    levelsBlocked:
      "Нет подтверждённых Lp: energy=0 → lpDb=null (не тишина). Теплокарта не показывается.",
    hint: "Нужна серверная ревизия. Backend: inline (Windows fixture_replay) или GitHub Actions (Linux SPPS, $0 на public repo).",
    needRevision:
      "Ревизия не зафиксирована — нажмите «Зафиксировать и рассчитать» или «Зафиксировать ревизию».",
    offlineBlocked:
      "Offline-черновик: откройте проект с API (Проекты → online), затем расчёт.",
    create: "Запустить расчёт",
    reviseAndRun: "Зафиксировать и рассчитать",
    commitRevision: "Зафиксировать ревизию",
    cancel: "Отменить",
    working: "Запрос…",
    statusTitle: "Статус задания",
    status: "Статус",
    errorCode: "Код ошибки",
    manifestTitle: "Манифест результата",
    levelsTitle: "Уровни в точках (punctual)",
    receiver: "Приёмник",
    energy: "Энергия (Σ)",
    lpDb: "Lp",
    mapLater: "Карта поверхности отложена (.csbin) — punctual не подменяют теплокарту.",
    noFakeLevels: "Нет подтверждённых уровней: нулевая энергия приёмника ≠ 0 дБ и ≠ тишина.",
    artifacts: "Артефакты",
    createError: "Не удалось создать задание",
    cancelError: "Не удалось отменить задание",
    pollError: "Ошибка опроса статуса",
    revisionError: "Не удалось зафиксировать ревизию",
    revisionLabel: "Ревизия сессии",
    planOverlayOn: "Lp на плане у рабочих мест обновлены по последнему job.",
    planOverlayReplay: "fixture_replay — эталон CI, не локальная сетка",
  },
  sync: {
    saved: "Сохранено на сервере",
    dirty: "Есть несохранённые изменения",
    conflict: "Конфликт версий (412)",
    offline: "Offline",
  },
} as const;

export type Dict = typeof ru;
