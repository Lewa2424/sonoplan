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
    hint: "Нужен серверный SPPS и зафиксированная ревизия. Тепловая карта не подставляется.",
    needSpps: "Для расчёта нужен серверный SPPS и ревизия модели. Очередь jobs — STG-04.",
  },
  sync: {
    saved: "Сохранено на сервере",
    dirty: "Есть несохранённые изменения",
    conflict: "Конфликт версий (412)",
    offline: "Offline",
  },
} as const;

export type Dict = typeof ru;
