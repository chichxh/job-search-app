import { Navigate, Outlet, Route, Routes, useLocation } from 'react-router-dom';

import './App.css';
import { useAuth } from './auth/useAuth.js';
import Layout from './components/Layout.jsx';
import RecommendationsPage from './pages/RecommendationsPage.jsx';
import SettingsPage from './pages/SettingsPage.jsx';
import ApplicationsPage from './pages/ApplicationsPage.jsx';
import VacanciesPage from './pages/VacanciesPage.jsx';
import VacancyDetailsPage from './pages/VacancyDetailsPage.jsx';
import LoginPage from './pages/LoginPage.jsx';
import RegisterPage from './pages/RegisterPage.jsx';
import Loading from './components/Loading.jsx';

function AuthStateScreen({ title, message }) {
  return (
    <section className="auth-page auth-page--status">
      <article className="auth-status-card">
        <p className="auth-card__eyebrow">Session</p>
        <h1>{title}</h1>
        <Loading message={message} />
      </article>
    </section>
  );
}

function ProtectedRoute() {
  const { isAuthenticated, isBootstrapping } = useAuth();
  const location = useLocation();

  if (isBootstrapping) {
    return <AuthStateScreen title="Проверяем доступ" message="Проверяем сессию и права доступа..." />;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  return <Outlet />;
}

function PublicOnlyRoute({ children }) {
  const { isAuthenticated, isBootstrapping } = useAuth();

  if (isBootstrapping) {
    return <AuthStateScreen title="Подготавливаем вход" message="Проверяем активную сессию..." />;
  }

  if (isAuthenticated) {
    return <Navigate to="/vacancies" replace />;
  }

  return children;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<PublicOnlyRoute><LoginPage /></PublicOnlyRoute>} />
      <Route path="/register" element={<PublicOnlyRoute><RegisterPage /></PublicOnlyRoute>} />

      <Route element={<ProtectedRoute />}>
        <Route element={<Layout />}>
          <Route path="/" element={<Navigate to="/vacancies" replace />} />
          <Route path="/vacancies" element={<VacanciesPage />} />
          <Route path="/vacancies/:vacancyId" element={<VacancyDetailsPage />} />
          <Route path="/recommendations" element={<RecommendationsPage />} />
          <Route path="/applications" element={<ApplicationsPage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Route>
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
