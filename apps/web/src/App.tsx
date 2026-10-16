import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { ru } from "./i18n/ru";
import { ProjectsPage } from "./pages/ProjectsPage";
import { ModelPage } from "./pages/ModelPage";
import { CalculationsPage } from "./pages/CalculationsPage";

export function App() {
  return (
    <div className="app-shell">
      <header className="app-header">
        <h1 className="app-title">{ru.appName}</h1>
      </header>
      <main className="app-main">
        <Routes>
          <Route path="/" element={<Navigate to="/projects" replace />} />
          <Route path="/projects" element={<ProjectsPage />} />
          <Route path="/model" element={<ModelPage />} />
          <Route path="/calculations" element={<CalculationsPage />} />
        </Routes>
      </main>
      <nav className="app-nav" aria-label="Основная навигация">
        <NavLink to="/projects" className={navClass}>
          {ru.nav.projects}
        </NavLink>
        <NavLink to="/model" className={navClass}>
          {ru.nav.model}
        </NavLink>
        <NavLink to="/calculations" className={navClass}>
          {ru.nav.calculations}
        </NavLink>
      </nav>
    </div>
  );
}

function navClass({ isActive }: { isActive: boolean }): string {
  return isActive ? "nav-link nav-link--active" : "nav-link";
}
