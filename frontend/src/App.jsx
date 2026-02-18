import { useEffect, useState } from 'react';

import './App.css';

const API_BASE_URL = '/api/v1';

function createTestVacancyPayload() {
  const suffix = Date.now();

  return {
    source: 'manual',
    external_id: `test-${suffix}`,
    title: `Тестовая вакансия #${suffix}`,
    company_name: 'Demo Company',
    location: 'Remote',
    salary_from: 150000,
    salary_to: 220000,
    currency: 'RUB',
    description: 'Автоматически созданная тестовая вакансия',
    status: 'open',
  };
}

export default function App() {
  const [vacancies, setVacancies] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [error, setError] = useState('');

  const loadVacancies = async () => {
    setIsLoading(true);
    setError('');

    try {
      const response = await fetch(`${API_BASE_URL}/vacancies`);
      if (!response.ok) {
        throw new Error('Не удалось загрузить вакансии');
      }

      const data = await response.json();
      setVacancies(data);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadVacancies();
  }, []);

  const handleAddTestVacancy = async () => {
    setIsCreating(true);
    setError('');

    try {
      const response = await fetch(`${API_BASE_URL}/vacancies`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(createTestVacancyPayload()),
      });

      if (!response.ok) {
        throw new Error('Не удалось добавить тестовую вакансию');
      }

      await loadVacancies();
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setIsCreating(false);
    }
  };

  return (
    <main className="vacancies-page">
      <header className="vacancies-header">
        <h1>Вакансии</h1>
        <button type="button" onClick={handleAddTestVacancy} disabled={isCreating}>
          {isCreating ? 'Добавляем...' : 'Добавить тестовую'}
        </button>
      </header>

      {isLoading ? <p>Загрузка...</p> : null}
      {error ? <p className="error">{error}</p> : null}

      {!isLoading && vacancies.length === 0 ? <p>Вакансий пока нет.</p> : null}

      <ul className="vacancies-list">
        {vacancies.map((vacancy) => (
          <li key={vacancy.id} className="vacancy-card">
            <h2>{vacancy.title}</h2>
            <p>
              <strong>Компания:</strong> {vacancy.company_name ?? '—'}
            </p>
            <p>
              <strong>Локация:</strong> {vacancy.location ?? '—'}
            </p>
            <p>
              <strong>Статус:</strong> {vacancy.status}
            </p>
          </li>
        ))}
      </ul>
    </main>
  );
}
