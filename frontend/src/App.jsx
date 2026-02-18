import { useEffect, useRef, useState } from 'react';

import './App.css';

const API_BASE_URL = 'http://localhost:8000';
const API_PREFIX = '/api/v1';

async function apiRequest(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${API_PREFIX}${path}`, options);
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed with status ${response.status}`);
  }
  return response.json();
}

const initialForm = {
  text: 'python backend',
  area: '',
  per_page: 20,
  pages_limit: 3,
};

export default function App() {
  const [vacancies, setVacancies] = useState([]);
  const [isLoadingVacancies, setIsLoadingVacancies] = useState(false);
  const [isStartingImport, setIsStartingImport] = useState(false);
  const [error, setError] = useState('');
  const [taskId, setTaskId] = useState('');
  const [taskState, setTaskState] = useState('');
  const [taskResult, setTaskResult] = useState(null);
  const [taskError, setTaskError] = useState('');
  const [form, setForm] = useState(initialForm);
  const pollIntervalRef = useRef(null);

  const loadVacancies = async () => {
    setIsLoadingVacancies(true);
    setError('');

    try {
      const data = await apiRequest('/vacancies');
      setVacancies(data);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setIsLoadingVacancies(false);
    }
  };

  useEffect(() => {
    loadVacancies();
  }, []);

  useEffect(
    () => () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
      }
    },
    [],
  );

  const stopPolling = () => {
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }
  };

  const pollTaskStatus = (id) => {
    stopPolling();

    pollIntervalRef.current = setInterval(async () => {
      try {
        const status = await apiRequest(`/tasks/${id}`);
        setTaskState(status.state);

        if (status.state === 'SUCCESS') {
          setTaskResult(status.result ?? null);
          setTaskError('');
          stopPolling();
          await loadVacancies();
        }

        if (status.state === 'FAILURE') {
          setTaskError(status.error || 'Import task failed');
          setTaskResult(null);
          stopPolling();
        }
      } catch (requestError) {
        setTaskError(requestError.message);
        stopPolling();
      }
    }, 2000);
  };

  const handleInputChange = (event) => {
    const { name, value } = event.target;
    setForm((prev) => ({ ...prev, [name]: value }));
  };

  const handleStartImport = async (event) => {
    event.preventDefault();
    setIsStartingImport(true);
    setError('');
    setTaskError('');
    setTaskResult(null);
    setTaskState('');

    const payload = {
      text: form.text.trim(),
      area: form.area.trim() === '' ? null : Number(form.area),
      per_page: Number(form.per_page),
      pages_limit: Number(form.pages_limit),
      fetch_details: true,
    };

    try {
      const data = await apiRequest('/import/hh', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });

      setTaskId(data.task_id);
      setTaskState('PENDING');
      pollTaskStatus(data.task_id);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setIsStartingImport(false);
    }
  };

  return (
    <main className="vacancies-page">
      <header className="vacancies-header">
        <h1>HH Import MVP</h1>
      </header>

      <form onSubmit={handleStartImport} className="vacancy-card" style={{ marginBottom: '16px' }}>
        <h2>Запуск импорта</h2>
        <p>
          <label>
            Text:{' '}
            <input name="text" value={form.text} onChange={handleInputChange} required />
          </label>
        </p>
        <p>
          <label>
            Area (optional):{' '}
            <input name="area" value={form.area} onChange={handleInputChange} type="number" />
          </label>
        </p>
        <p>
          <label>
            Per page:{' '}
            <input
              name="per_page"
              value={form.per_page}
              onChange={handleInputChange}
              type="number"
              min={1}
              max={100}
              required
            />
          </label>
        </p>
        <p>
          <label>
            Pages limit:{' '}
            <input
              name="pages_limit"
              value={form.pages_limit}
              onChange={handleInputChange}
              type="number"
              min={1}
              max={20}
              required
            />
          </label>
        </p>

        <button type="submit" disabled={isStartingImport}>
          {isStartingImport ? 'Starting...' : 'Start HH Import'}
        </button>
      </form>

      {taskId ? (
        <section className="vacancy-card" style={{ marginBottom: '16px' }}>
          <h2>Task status</h2>
          <p>
            <strong>Task ID:</strong> {taskId}
          </p>
          <p>
            <strong>State:</strong> {taskState || '—'}
          </p>
          {taskResult ? <pre>{JSON.stringify(taskResult, null, 2)}</pre> : null}
          {taskError ? <p className="error">{taskError}</p> : null}
        </section>
      ) : null}

      {isLoadingVacancies ? <p>Загрузка вакансий...</p> : null}
      {error ? <p className="error">{error}</p> : null}

      {!isLoadingVacancies && vacancies.length === 0 ? <p>Вакансий пока нет.</p> : null}

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
              <strong>Источник:</strong> {vacancy.source}
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
