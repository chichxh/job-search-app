import { useCallback, useEffect, useMemo, useState } from 'react';

import {
  getRecommendations,
  getTask,
  recomputeRecommendations,
} from '../api/endpoints.js';
import { DEFAULT_PROFILE_ID } from '../config.js';
import ErrorBanner from '../components/ErrorBanner.jsx';
import Loading from '../components/Loading.jsx';
import VacancyCard from '../components/VacancyCard.jsx';
import { loadJobSearchSettings } from '../utils/settings.js';

function formatScore(score) {
  if (score == null || Number.isNaN(Number(score))) {
    return '—';
  }

  return Number(score).toFixed(3);
}

export default function RecommendationsPage() {
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
        DEFAULT_PROFILE_ID,
        settings.recommendationsLimit,
      );
      setRecommendations(response.items ?? []);
    } catch (requestError) {
      setError(requestError.message || 'Failed to load recommendations.');
    } finally {
      setLoading(false);
    }
  }, [settings.recommendationsLimit]);

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
        DEFAULT_PROFILE_ID,
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
      <h1>Recommendations</h1>

      <div className="recommendations-toolbar" aria-label="Recommendations controls">
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
          <span>Скрывать weak</span>
        </label>
      </div>

      <p className="loading">
        limit: {settings.recommendationsLimit} · hideReject: {settings.hideReject ? 'on' : 'off'}
      </p>

      {taskId ? (
        <p className="loading">Задача {taskId}: {taskState}</p>
      ) : taskState === 'SUCCESS' ? (
        <p className="loading">Рекомендации пересчитаны.</p>
      ) : null}

      {taskError ? <ErrorBanner message={taskError} /> : null}

      {loading ? <Loading message="Loading recommendations..." /> : null}
      {!loading && error ? <ErrorBanner message={error} /> : null}

      {!loading && !error ? (
        visibleRecommendations.length > 0 ? (
          <div className="recommendations-list">
            {visibleRecommendations.map((item) => (
              <article className="recommendations-item" key={item.id}>
                <VacancyCard
                  title={item.title}
                  company={item.company_name ?? 'Company not specified'}
                  location={item.location ?? 'Location not specified'}
                  salary="Open vacancy"
                  to={`/vacancies/${item.id}`}
                />
                <div className="recommendations-item__score">
                  <p className="recommendations-item__metric">
                    final_score: <strong>{formatScore(item.final_score)}</strong>
                  </p>
                  <p className={`recommendations-item__verdict recommendations-item__verdict--${item.verdict}`}>
                    verdict: {item.verdict}
                  </p>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <p className="loading">No recommendations for selected filters.</p>
        )
      ) : null}
    </section>
  );
}
