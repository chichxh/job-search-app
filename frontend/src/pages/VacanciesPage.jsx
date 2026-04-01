import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';

import { getTask, getVacancies, startHhImport } from '../api/endpoints.js';
import ErrorBanner from '../components/ErrorBanner.jsx';
import Loading from '../components/Loading.jsx';
import PageHeader from '../components/ui/PageHeader.jsx';
import SectionCard from '../components/ui/SectionCard.jsx';
import StatusPill from '../components/ui/StatusPill.jsx';
import { formatDateTime, formatSalary, getSafeText } from '../utils/formatters.js';

const DEFAULT_IMPORT_PAYLOAD = {
  text: 'python developer',
  area: 1,
  per_page: 20,
  pages_limit: 2,
  fetch_details: true,
};

const IMPORT_POLL_INTERVAL_MS = 2000;

export default function VacanciesPage() {
  const [vacancies, setVacancies] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');
  const [onlyOpen, setOnlyOpen] = useState(false);
  const [isImporting, setIsImporting] = useState(false);
  const [importTaskId, setImportTaskId] = useState('');
  const [importState, setImportState] = useState('IDLE');
  const [importError, setImportError] = useState('');
  const [importSuccess, setImportSuccess] = useState('');

  useEffect(() => {
    let isMounted = true;

    async function loadVacancies() {
      setLoading(true);
      setError('');

      try {
        const response = await getVacancies();
        if (isMounted) {
          setVacancies(Array.isArray(response) ? response : []);
        }
      } catch (requestError) {
        if (isMounted) {
          setError(requestError.message || 'Failed to load vacancies.');
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    }

    loadVacancies();

    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    if (!importTaskId) {
      return undefined;
    }

    let isActive = true;

    async function pollImportStatus() {
      try {
        const task = await getTask(importTaskId);
        if (!isActive) {
          return;
        }

        setImportState(task.state ?? 'PENDING');

        if (task.state === 'SUCCESS') {
          setImportError('');
          setImportSuccess('Импорт вакансий завершён. Обновляем список...');
          setImportTaskId('');
          setIsImporting(false);

          const response = await getVacancies();
          if (!isActive) {
            return;
          }
          setVacancies(Array.isArray(response) ? response : []);
          setImportSuccess('Импорт вакансий завершён.');
        }

        if (task.state === 'FAILURE') {
          setImportError(task.error || 'Не удалось выполнить импорт вакансий.');
          setImportSuccess('');
          setImportTaskId('');
          setIsImporting(false);
        }
      } catch (requestError) {
        if (!isActive) {
          return;
        }

        setImportError(requestError.message || 'Не удалось обновить статус импорта.');
        setImportSuccess('');
        setImportTaskId('');
        setIsImporting(false);
      }
    }

    const intervalId = setInterval(pollImportStatus, IMPORT_POLL_INTERVAL_MS);
    pollImportStatus();

    return () => {
      isActive = false;
      clearInterval(intervalId);
    };
  }, [importTaskId]);

  const normalizedSearch = search.trim().toLowerCase();

  const filteredVacancies = useMemo(() => {
    return vacancies.filter((vacancy) => {
      const title = vacancy.title?.toLowerCase() ?? '';
      const company = vacancy.company_name?.toLowerCase() ?? vacancy.company?.toLowerCase() ?? '';
      const location = vacancy.location?.toLowerCase() ?? '';
      const matchesSearch =
        normalizedSearch.length === 0
        || title.includes(normalizedSearch)
        || company.includes(normalizedSearch)
        || location.includes(normalizedSearch);

      if (!matchesSearch) {
        return false;
      }

      if (!onlyOpen) {
        return true;
      }

      return vacancy.status?.toLowerCase() === 'open';
    });
  }, [normalizedSearch, onlyOpen, vacancies]);

  const emptyStateMessage = vacancies.length === 0
    ? 'Пока нет вакансий. Импортируйте вакансии, чтобы они появились здесь.'
    : 'Нет вакансий по текущим фильтрам. Попробуйте изменить поиск или отключить фильтр «Только открытые».';

  async function handleStartImport() {
    setImportError('');
    setImportSuccess('');
    setImportState('PENDING');
    setIsImporting(true);

    try {
      const response = await startHhImport(DEFAULT_IMPORT_PAYLOAD);
      setImportTaskId(response.task_id);
    } catch (requestError) {
      setImportError(requestError.message || 'Не удалось запустить импорт вакансий.');
      setImportState('FAILURE');
      setIsImporting(false);
    }
  }

  return (
    <section className="page-stack">
      <PageHeader
        eyebrow="Vacancy Discovery"
        title="Вакансии"
        subtitle="Импортируйте поток вакансий и поддерживайте чистый shortlist для мэтчинга и генерации документов."
      />

      <SectionCard
        className="import-area"
        title="Импорт из HH"
        subtitle="Запускает фоновую задачу импорта и обновляет список вакансий после завершения."
        actions={(
          <button
            className="recommendations-toolbar__button"
            type="button"
            onClick={handleStartImport}
            disabled={isImporting}
          >
            {isImporting ? 'Идёт импорт...' : 'Выгрузить вакансии из HH'}
          </button>
        )}
      >
        <div className="inline-status-row">
          <StatusPill tone={isImporting ? 'info' : importSuccess ? 'success' : 'neutral'}>
            {isImporting ? `Task ${importTaskId || '—'} · ${importState}` : importSuccess || 'Готово к запуску импорта'}
          </StatusPill>
          <p className="flow-hint">После импорта перейдите в <Link className="vacancy-details__link" to="/recommendations">Recommendations</Link> и пересчитайте ranking.</p>
        </div>
      </SectionCard>

      {importError ? <ErrorBanner message={importError} /> : null}

      <SectionCard className="vacancy-list-shell" title="Список вакансий" subtitle={`Всего: ${vacancies.length} · Показано: ${filteredVacancies.length}`}>
        <div className="toolbar toolbar--subtle vacancy-filters" aria-label="Vacancy filters">
          <input
            className="vacancy-filters__search"
            type="search"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Поиск по названию, компании или локации"
            aria-label="Поиск вакансий"
          />
          <label className="vacancy-filters__toggle">
            <input
              type="checkbox"
              checked={onlyOpen}
              onChange={(event) => setOnlyOpen(event.target.checked)}
            />
            <span>Только открытые</span>
          </label>
        </div>

        {loading ? <Loading message="Загружаем вакансии..." /> : null}
        {!loading && error ? <ErrorBanner message={error} /> : null}

        {!loading && !error ? (
          filteredVacancies.length > 0 ? (
            <div className="vacancy-list">
              {filteredVacancies.map((vacancy) => (
                <Link key={vacancy.id} className="vacancy-row" to={`/vacancies/${vacancy.id}`}>
                  <div>
                    <p className="vacancy-row__title">{getSafeText(vacancy.title, 'Название вакансии не указано')}</p>
                    <p className="vacancy-row__meta">{getSafeText(vacancy.company_name ?? vacancy.company, 'Компания не указана')} · {getSafeText(vacancy.location, 'Локация не указана')}</p>
                  </div>
                  <p className="vacancy-row__salary">{formatSalary(vacancy)}</p>
                  <StatusPill tone={vacancy.status?.toLowerCase() === 'open' ? 'success' : 'neutral'}>{vacancy.status ?? 'unknown'}</StatusPill>
                  <p className="vacancy-row__date">updated {formatDateTime(vacancy.updated_at) ?? '—'}</p>
                </Link>
              ))}
            </div>
          ) : (
            <p className="empty-state">{emptyStateMessage}</p>
          )
        ) : null}
      </SectionCard>
    </section>
  );
}
