import { Navigate, Route, Routes } from 'react-router-dom';

import './App.css';
import Layout from './components/Layout.jsx';
import RecommendationsPage from './pages/RecommendationsPage.jsx';
import SettingsPage from './pages/SettingsPage.jsx';
import VacanciesPage from './pages/VacanciesPage.jsx';
import VacancyDetailsPage from './pages/VacancyDetailsPage.jsx';

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Navigate to="/vacancies" replace />} />
        <Route path="/vacancies" element={<VacanciesPage />} />
        <Route path="/vacancies/:vacancyId" element={<VacancyDetailsPage />} />
        <Route path="/recommendations" element={<RecommendationsPage />} />
        <Route path="/settings" element={<SettingsPage />} />
      </Route>
    </Routes>
  );
}
