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
    hint: "План сверху (X,Y). Покрытия и оборудование — на панели. Стеллажи/перегородки на плане; в расчёте SPPS пока коробка + материалы + источники (без mesh препятствий).",
    noProject: "Проект не выбран — перейдите в «Проекты».",
    viewTop: "Сверху",
    todo3d: "3D-вид (коробка комнаты) — позже",
    coatings: "Покрытия",
    coatingsHint: "Один материал на ограждения (пол/стены/потолок). α оценочные.",
    equipment: "Оборудование",
    placeEquipment: "Поставить оборудование",
    placeWorkplaceNear: "и РМ рядом",
    obstacle: "Препятствие",
    placeRack: "Стеллаж",
    placeCabinet: "Шкаф",
    placePartition: "Перегородка",
    solidsNote:
      "Стеллажи и перегородки сохраняются в модели; в текущем SPPS-расчёте в mesh не входят.",
    calculate: "Рассчитать",
    spectrumAdvanced: "Полосы Lw (подробно)",
    lwTypical: "Типовой шум Lw, дБ",
    staleLp:
      "Уровни на плане от старого расчёта — модель изменена. Нажмите «Рассчитать».",
  },
  calculations: {
    title: "Расчёты",
    empty: "Очередь расчётов недоступна.",
    lead: "Один расчёт = одна ревизия. Карта — только из SPPS (сечение), не «рисунок».",
    levelsReady:
      "Punctual уровни (Lp, дБ) из реального SPPS .recp. Нулевая энергия ≠ 0 дБ.",
    levelsReplay:
      "Windows MVP: уровни с эталонного CI-прогона (fixture_replay), не локальный SPPS по вашей сетке.",
    levelsActions:
      "Linux SPPS через GitHub Actions. Phase 2A — коробка + ваши Lw/РМ/материалы.",
    levelsActionsBox:
      "Linux SPPS (Actions): коробка AABB + источники/РМ/материалы. Препятствия в mesh — позже.",
    levelsPending:
      "Расчёт в очереди GitHub Actions… обычно несколько минут.",
    levelsIdle:
      "Нажмите «Рассчитать» — до job нет Lp (это не «тишина»).",
    levelsBlocked:
      "Нет подтверждённых Lp: energy=0 → lpDb=null (не тишина).",
    levelsStale:
      "Черновик изменён после расчёта — цифры на плане устарели. Рассчитайте снова.",
    hint: "Нужен онлайн-проект (API). Расчёт идёт на Linux SPPS через Actions или inline/fixture.",
    needRevision:
      "Нужна ревизия — нажмите «Рассчитать» (зафиксирует и запустит).",
    offlineBlocked:
      "Offline-черновик: откройте проект с API (Проекты → online), затем расчёт.",
    create: "Рассчитать",
    reviseAndRun: "Рассчитать",
    commitRevision: "Только ревизия",
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
    mapTitle: "Карта сечения (SPPS)",
    mapLater: "Карта сечения ещё не в манифесте — punctual не подменяют теплокарту.",
    mapReady:
      "Горизонтальное сечение SPPS (энергия ячеек → Lp). Это не Lp у рабочих мест и не интерполяция точек.",
    mapLegend: "Шкала цвета",
    mapLegendHint: "Авто по min/max ячеек с энергией на этой карте (не пороги 80/90/100).",
    mapScaleOnPlan: "Карта сечения · шкала авто",
    noFakeLevels: "Нет подтверждённых уровней: нулевая энергия приёмника ≠ 0 дБ и ≠ тишина.",
    artifacts: "Артефакты",
    createError: "Не удалось создать задание",
    cancelError: "Не удалось отменить задание",
    pollError: "Ошибка опроса статуса",
    revisionError: "Не удалось зафиксировать ревизию",
    revisionLabel: "Ревизия сессии",
    planOverlayOn: "Lp на плане у рабочих мест обновлены по последнему job.",
    planOverlayReplay: "эталон/fixture — не полная ваша геометрия",
  },
  sync: {
    saved: "Сохранено на сервере",
    dirty: "Есть несохранённые изменения",
    conflict: "Конфликт версий (412)",
    offline: "Offline",
  },
} as const;

export type Dict = typeof ru;
