import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';

import { getTailoring, getVacancyById } from '../api/endpoints.js';
import { DEFAULT_PROFILE_ID } from '../config.js';
import ErrorBanner from '../components/ErrorBanner.jsx';
import Loading from '../components/Loading.jsx';
import { formatDateTime, formatSalary, getSafeText } from '../utils/formatters.js';

function toList(value) {
  return Array.isArray(value) ? value : [];
}

function formatConfidence(value) {
  if (value == null || Number.isNaN(Number(value))) {
    return '—';
  }

  return Number(value).toFixed(2);
}

export default function VacancyDetailsPage() {
  const { vacancyId } = useParams();

  const [vacancy, setVacancy] = useState(null);
  const [tailoring, setTailoring] = useState(null);
  const [loading, setLoading] = useState(true);
  const [vacancyError, setVacancyError] = useState('');
  const [tailoringError, setTailoringError] = useState('');
  const [isRefreshingTailoring, setIsRefreshingTailoring] = useState(false);

  const loadTailoring = useCallback(async () => {
    setTailoringError('');

    try {
      const tailoringResponse = await getTailoring(DEFAULT_PROFILE_ID, vacancyId);
      setTailoring(tailoringResponse);
    } catch (requestError) {
      setTailoring(null);
      setTailoringError(requestError.message || 'Не удалось загрузить мэтчинг.');
    }
  }, [vacancyId]);

  const refreshTailoring = useCallback(async () => {
    setIsRefreshingTailoring(true);
    await loadTailoring();
    setIsRefreshingTailoring(false);
  }, [loadTailoring]);

  useEffect(() => {
    let isActive = true;

    async function loadPageData() {
      setLoading(true);
      setVacancyError('');
      setTailoringError('');

      try {
        const [vacancyResponse, tailoringResponse] = await Promise.all([
          getVacancyById(vacancyId),
          getTailoring(DEFAULT_PROFILE_ID, vacancyId),
        ]);

        if (!isActive) {
          return;
        }

        setVacancy(vacancyResponse);
        setTailoring(tailoringResponse);
      } catch {
        if (!isActive) {
          return;
        }

        try {
          const vacancyResponse = await getVacancyById(vacancyId);
          if (isActive) {
            setVacancy(vacancyResponse);
          }
        } catch (innerError) {
          if (isActive) {
            setVacancy(null);
            setVacancyError(innerError.message || 'Не удалось загрузить вакансию.');
          }
        }

        try {
          const tailoringResponse = await getTailoring(DEFAULT_PROFILE_ID, vacancyId);
          if (isActive) {
            setTailoring(tailoringResponse);
          }
        } catch (innerError) {
          if (isActive) {
            setTailoring(null);
            setTailoringError(innerError.message || 'Не удалось загрузить мэтчинг.');
          }
        }
      } finally {
        if (isActive) {
          setLoading(false);
        }
      }
    }

    loadPageData();

    return () => {
      isActive = false;
    };
  }, [vacancyId]);

  const explanation = tailoring?.explanation;
  const evidenceItems = useMemo(() => {
    if (Array.isArray(tailoring?.evidence)) {
      return tailoring.evidence;
    }

    if (Array.isArray(explanation?.evidence)) {
      return explanation.evidence;
    }

    return [];
  }, [tailoring?.evidence, explanation?.evidence]);

  const finalScore = explanation?.final?.score ?? explanation?.final_score;
  const verdict = explanation?.final?.verdict ?? explanation?.verdict;

  const keywordsToAdd = toList(explanation?.keywords_to_add);
  const missingMustHave = toList(explanation?.missing_must_have);
  const missingNiceToHave = toList(explanation?.missing_nice_to_have);
  const coverLetterPoints = toList(explanation?.cover_letter_points);

  const hasTailoringSections = Boolean(
    finalScore != null
      || verdict
      || keywordsToAdd.length
      || missingMustHave.length
      || missingNiceToHave.length
      || coverLetterPoints.length
      || evidenceItems.length,
  );

  return (
    <section className="page-stack">
      <h1>Vacancy details</h1>

      {loading ? <Loading message="Loading vacancy details..." /> : null}
      {!loading && vacancyError ? <ErrorBanner message={vacancyError} /> : null}

      {!loading && vacancy ? (
        <article className="vacancy-details">
          <h2 className="vacancy-details__title">{vacancy.title}</h2>
          <div className="vacancy-details__meta-grid">
            <p><strong>Компания:</strong> {getSafeText(vacancy.company_name ?? vacancy.company, 'Не указана')}</p>
            <p><strong>Локация:</strong> {getSafeText(vacancy.location, 'Не указана')}</p>
            <p><strong>Зарплата:</strong> {formatSalary(vacancy, { emptyLabel: 'Не указана', fromLabel: 'от', toLabel: 'до' })}</p>
            <p><strong>Статус:</strong> {vacancy.status ?? 'Не указан'}</p>
            <p><strong>Источник:</strong> {vacancy.source ?? 'Не указан'}</p>
            {formatDateTime(vacancy.created_at) ? <p><strong>Создано:</strong> {formatDateTime(vacancy.created_at)}</p> : null}
            {formatDateTime(vacancy.updated_at) ? <p><strong>Обновлено:</strong> {formatDateTime(vacancy.updated_at)}</p> : null}
            <p>
              <strong>Ссылка:</strong>{' '}
              {vacancy.url ? (
                <a href={vacancy.url} target="_blank" rel="noreferrer">{vacancy.url}</a>
              ) : (
                'Не указана'
              )}
            </p>
          </div>
          <h3 className="vacancy-details__section-title">Описание</h3>
          <pre className="vacancy-details__description">{vacancy.description ?? 'Описание отсутствует.'}</pre>
        </article>
      ) : null}

      <section className="vacancy-details__matching">
        <div className="vacancy-details__matching-header">
          <h2 className="vacancy-details__section-title">Мэтчинг</h2>
          <button
            className="recommendations-toolbar__button"
            type="button"
            onClick={refreshTailoring}
            disabled={loading || isRefreshingTailoring}
          >
            Обновить мэтчинг
          </button>
        </div>

        {isRefreshingTailoring ? <Loading message="Обновляем мэтчинг..." /> : null}

        {!loading && (tailoringError || !tailoring) ? (
          <div className="vacancy-details__hint">
            {tailoringError ? <ErrorBanner message={tailoringError} /> : null}
            <p>Пересчитайте рекомендации.</p>
            <Link className="vacancy-details__link" to="/recommendations">
              Перейти на /recommendations
            </Link>
          </div>
        ) : null}

        {!loading && tailoring && hasTailoringSections ? (
          <div className="vacancy-details__matching-content">
            {(finalScore != null || verdict) ? (
              <p className="vacancy-details__score">
                {finalScore != null ? <>final_score: <strong>{formatConfidence(finalScore)}</strong></> : null}
                {finalScore != null && verdict ? ' · ' : null}
                {verdict ? <>verdict: <strong>{verdict}</strong></> : null}
              </p>
            ) : null}

            {keywordsToAdd.length ? (
              <div>
                <h3 className="vacancy-details__section-title">keywords_to_add</h3>
                <ul>
                  {keywordsToAdd.map((keyword) => (
                    <li key={keyword}>{keyword}</li>
                  ))}
                </ul>
              </div>
            ) : null}

            {missingMustHave.length ? (
              <div>
                <h3 className="vacancy-details__section-title">missing_must_have</h3>
                <ul>
                  {missingMustHave.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>
            ) : null}

            {missingNiceToHave.length ? (
              <div>
                <h3 className="vacancy-details__section-title">missing_nice_to_have</h3>
                <ul>
                  {missingNiceToHave.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>
            ) : null}

            {coverLetterPoints.length ? (
              <div>
                <h3 className="vacancy-details__section-title">cover_letter_points</h3>
                <ul>
                  {coverLetterPoints.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>
            ) : null}

            {evidenceItems.length ? (
              <div>
                <h3 className="vacancy-details__section-title">evidence</h3>
                <ul>
                  {evidenceItems.map((item, index) => {
                    const text = item.text ?? item.evidence_text ?? String(item);
                    const confidence = item.confidence;

                    return (
                      <li key={`${text}-${index}`}>
                        {text} {confidence != null ? `(${formatConfidence(confidence)})` : ''}
                      </li>
                    );
                  })}
                </ul>
              </div>
            ) : null}
          </div>
        ) : null}

        {!loading && tailoring && !hasTailoringSections ? (
          <details>
            <summary>Raw tailoring JSON</summary>
            <pre className="vacancy-details__description">{JSON.stringify(tailoring, null, 2)}</pre>
          </details>
        ) : null}
      </section>
    </section>
  );
}
