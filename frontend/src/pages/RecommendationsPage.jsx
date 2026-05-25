import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';

import {
  getRecommendations,
  getTask,
  recomputeRecommendations,
} from '../api/endpoints.js';
import { useAuth } from '../auth/useAuth.js';
import ErrorBanner from '../components/ErrorBanner.jsx';
import Loading from '../components/Loading.jsx';
import MetricTile from '../components/ui/MetricTile.jsx';
import PageHeader from '../components/ui/PageHeader.jsx';
import SectionCard from '../components/ui/SectionCard.jsx';
import VerdictBadge from '../components/ui/VerdictBadge.jsx';
import { formatDateTime, getSafeText } from '../utils/formatters.js';
import { loadJobSearchSettings } from '../utils/settings.js';

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

  const topScore = visibleRecommendations[0]?.final_score;

  return (
    <section className="page-stack">
      <PageHeader
        eyebrow="Ranking Workspace"
        title="Рекомендации"
        subtitle="Ключевой экран ранжирования: пересчёт, скоринг, вердикт и быстрый переход к деталям вакансии."
      />

      <SectionCard
        className="recommendations-hero"
        title="Пересчёт рекомендаций"
        subtitle="Обновите рекомендации на основе текущего профиля."
        actions={(
          <div className="button-group">
            <button className="button" type="button" onClick={handleRecompute} disabled={Boolean(taskId)}>
              Пересчитать рекомендации
            </button>
            <button className="button button--secondary" type="button" onClick={handleReloadSettings}>Обновить параметры</button>
          </div>
        )}
      >
        <div className="recommendations-metrics">
          <MetricTile label="Видимых рекомендаций" value={visibleRecommendations.length} hint="После фильтров weak/reject" />
          <MetricTile label="Лучшая оценка" value={formatScore(topScore)} tone="info" hint="Лучший вариант в текущем списке" />
          <MetricTile label="Лимит" value={settings.recommendationsLimit} hint={`hideReject: ${settings.hideReject ? 'on' : 'off'}`} />
        </div>
        <label className="vacancy-filters__toggle">
          <input
            type="checkbox"
            checked={hideWeak}
            onChange={(event) => setHideWeak(event.target.checked)}
          />
          <span>Скрывать слабые совпадения</span>
        </label>
        {taskId ? (
          <p className="info-banner">Идёт пересчёт рекомендаций: {taskState}</p>
        ) : taskState === 'SUCCESS' ? (
          <p className="success-banner">Рекомендации пересчитаны.</p>
        ) : null}
      </SectionCard>

      {taskError ? <ErrorBanner message={taskError} /> : null}

      <SectionCard title="Список рекомендаций" subtitle="Сначала самые сильные кандидаты на отклик.">
        {loading ? <Loading message="Загружаем рекомендации..." /> : null}
        {!loading && error ? <ErrorBanner message={error} /> : null}

        {!loading && !error ? (
          visibleRecommendations.length > 0 ? (
            <div className="recommendations-ranked-list">
              {visibleRecommendations.map((item, index) => (
                <article className="recommendation-row" key={item.id}>
                  <div className="recommendation-row__rank">#{index + 1}</div>
                  <div className="recommendation-row__main">
                    <p className="recommendation-row__title">{getSafeText(item.title, 'Название вакансии не указано')}</p>
                    <p className="recommendation-row__meta">{getSafeText(item.company_name ?? item.company, 'Компания не указана')} · {getSafeText(item.location, 'Локация не указана')}</p>
                    <p className="recommendation-row__dates">updated {formatDateTime(item.updated_at) ?? '—'} · created {formatDateTime(item.created_at) ?? '—'}</p>
                  </div>
                  <div className="recommendation-row__scorebox">
                    <p className="recommendation-row__score">{formatScore(item.final_score)}</p>
                    <p className="recommendation-row__score-label">Оценка</p>
                    <VerdictBadge verdict={item.verdict} />
                  </div>
                  <div className="recommendation-row__actions">
                    <Link className="recommendation-row__link" to={`/vacancies/${item.id}`}>Открыть вакансию →</Link>
                    <p className="recommendation-row__next">Следующий шаг: проверить мэтчинг и документы</p>
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
      </SectionCard>
    </section>
  );
}
