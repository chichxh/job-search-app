import { useCallback, useEffect, useMemo, useState } from 'react';

import {
  getRecommendations,
  getTask,
  recomputeRecommendations,
} from '../api/endpoints.js';
import ErrorBanner from '../components/ErrorBanner.jsx';
import Loading from '../components/Loading.jsx';
import VacancyCard from '../components/VacancyCard.jsx';
import { formatDateTime, getSafeText } from '../utils/formatters.js';
import { loadJobSearchSettings } from '../utils/settings.js';
import { useAuth } from '../auth/useAuth.js';

function formatScore(score) {
  if (score == null || Number.isNaN(Number(score))) {
    return '—';
  }

  return Number(score).toFixed(3);
}

export default function RecommendationsPage() {
  const { profileId } = useAuth();
  const [recommendations, setRecommendations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [taskId, setTaskId] = useState('');
  const [taskState, setTaskState] = useState('IDLE');
  const [taskError, setTaskError] = useState('');
  const [hideWeak, setHideWeak] = useState(false);
  const [settings, setSettings] = useState(loadJobSearchSettings());

  const loadRecommendations = useCallback(async () => {
    setLoading(true);
    setError('');

    try {
      const response = await getRecommendations(
        profileId,
        settings.recommendationsLimit,
      );
      setRecommendations(response.items ?? []);
    } catch (requestError) {
      setError(requestError.message || 'Failed to load recommendations.');
    } finally {
      setLoading(false);
    }
  }, [profileId, settings.recommendationsLimit]);

  useEffect(() => {
    loadRecommendations();
  }, [loadRecommendations]);

  useEffect(() => {
    if (!taskId) {
      return undefined;
    }

    let intervalId;
    let isActive = true;

    async function pollTaskStatus() {
      try {
        const task = await getTask(taskId);
        if (!isActive) {
          return;
        }

        setTaskState(task.state);

        if (task.state === 'SUCCESS') {
          setTaskError('');
          setTaskId('');
          await loadRecommendations();
          return;
        }

        if (task.state === 'FAILURE') {
          setTaskError(task.error || 'Recompute task failed.');
          setTaskId('');
        }
      } catch (requestError) {
        if (!isActive) {
          return;
        }

        setTaskError(requestError.message || 'Failed to poll task status.');
        setTaskId('');
        setTaskState('FAILURE');
      }
    }

    pollTaskStatus();
    intervalId = setInterval(pollTaskStatus, 2000);

    return () => {
      isActive = false;
      clearInterval(intervalId);
    };
  }, [taskId, loadRecommendations]);

  const visibleRecommendations = useMemo(() => {
    return recommendations.filter((item) => {
      const verdict = item.verdict?.toLowerCase();

      if (settings.hideReject && verdict === 'reject') {
        return false;
      }

      if (hideWeak && verdict === 'weak') {
        return false;
      }

      return true;
    });
  }, [hideWeak, recommendations, settings.hideReject]);

  async function handleRecompute() {
    setTaskError('');

    try {
      const response = await recomputeRecommendations(
        profileId,
        settings.recommendationsLimit,
      );
      setTaskId(response.task_id);
      setTaskState('PENDING');
    } catch (requestError) {
      setTaskError(requestError.message || 'Failed to start recommendations recompute.');
      setTaskState('FAILURE');
    }
  }

  function handleReloadSettings() {
    const nextSettings = loadJobSearchSettings();
    setSettings(nextSettings);
  }

  return (
    <section className="page-stack">
      <header className="page-header">
        <div>
          <h1>Рекомендации</h1>
          <p className="page-header__subtitle">Пересчитывайте ранжирование и фокусируйтесь на сильнейших вакансиях.</p>
        </div>
      </header>

      <div className="toolbar recommendations-toolbar" aria-label="Recommendations controls">
        <button
          className="recommendations-toolbar__button"
          type="button"
          onClick={handleRecompute}
          disabled={Boolean(taskId)}
        >
          Пересчитать рекомендации
        </button>

        <button
          className="recommendations-toolbar__button recommendations-toolbar__button--secondary"
          type="button"
          onClick={handleReloadSettings}
        >
          Обновить настройки
        </button>

        <label className="vacancy-filters__toggle">
          <input
            type="checkbox"
            checked={hideWeak}
            onChange={(event) => setHideWeak(event.target.checked)}
          />
          <span>Скрывать слабые</span>
        </label>
      </div>

      <p className="info-banner">лимит: {settings.recommendationsLimit} · hideReject: {settings.hideReject ? 'вкл' : 'выкл'}</p>

      {taskId ? (
        <p className="info-banner">Задача {taskId}: {taskState}</p>
      ) : taskState === 'SUCCESS' ? (
        <p className="success-banner">Рекомендации пересчитаны.</p>
      ) : null}

      {taskState === 'SUCCESS' && !taskId ? (
        <p className="flow-hint">
          Следующий шаг: откройте карточку вакансии, проверьте tailoring и сгенерируйте draft-документы.
        </p>
      ) : null}

      {taskError ? <ErrorBanner message={taskError} /> : null}

      {loading ? <Loading message="Загружаем рекомендации..." /> : null}
      {!loading && error ? <ErrorBanner message={error} /> : null}

      {!loading && !error ? (
        visibleRecommendations.length > 0 ? (
          <div className="recommendations-list">
            {visibleRecommendations.map((item) => (
              <article className="recommendations-item" key={item.id}>
                <VacancyCard
                  title={getSafeText(item.title, 'Название вакансии не указано')}
                  company={getSafeText(item.company_name ?? item.company, 'Компания не указана')}
                  location={getSafeText(item.location, 'Локация не указана')}
                  salary="Открытая вакансия"
                  createdAt={formatDateTime(item.created_at)}
                  updatedAt={formatDateTime(item.updated_at)}
                  to={`/vacancies/${item.id}`}
                />
                <div className="recommendations-item__score">
                  <p className="recommendations-item__metric">
                    итоговый_скор:  <strong>{formatScore(item.final_score)}</strong>
                  </p>
                  <p className={`recommendations-item__verdict recommendations-item__verdict--${item.verdict}`}>
                    вердикт: {item.verdict}
                  </p>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <p className="empty-state">
            {recommendations.length === 0
              ? 'Пока нет рекомендаций. Нажмите «Пересчитать рекомендации».'
              : 'Нет рекомендаций по текущим фильтрам. Попробуйте отключить фильтр weak/reject.'}
          </p>
        )
      ) : null}

      {!loading && !error && visibleRecommendations.length > 0 ? (
        <p className="flow-hint">
          Откройте любую вакансию из списка, чтобы перейти к tailoring → generate → approve.
        </p>
      ) : null}
    </section>
  );
}
