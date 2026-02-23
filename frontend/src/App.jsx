import { Link, Navigate, Outlet, Route, Routes } from 'react-router-dom';

import './App.css';
import RecommendationsPage from './pages/RecommendationsPage.jsx';
import SettingsPage from './pages/SettingsPage.jsx';
import VacanciesPage from './pages/VacanciesPage.jsx';
import VacancyDetailsPage from './pages/VacancyDetailsPage.jsx';

function AppLayout() {
  return (
    <div className="app-layout">
      <header className="top-nav">
        <nav>
          <ul className="nav-links">
            <li>
              <Link to="/vacancies">Vacancies</Link>
            </li>
            <li>
              <Link to="/recommendations">Recommendations</Link>
            </li>
            <li>
              <Link to="/vacancies/1">Vacancy Details</Link>
            </li>
            <li>
              <Link to="/settings">Settings</Link>
            </li>
          </ul>
        </nav>
      </header>
      <main className="page-content">
        <Outlet />
      </main>
    </div>
  );
}

export default function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route path="/" element={<Navigate to="/vacancies" replace />} />
        <Route path="/vacancies" element={<VacanciesPage />} />
        <Route path="/vacancies/:vacancyId" element={<VacancyDetailsPage />} />
        <Route path="/recommendations" element={<RecommendationsPage />} />
        <Route path="/settings" element={<SettingsPage />} />
      </Route>
    </Routes>
  );
}
