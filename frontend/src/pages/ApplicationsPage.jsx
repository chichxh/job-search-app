import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';

import ErrorBanner from '../components/ErrorBanner.jsx';
import Loading from '../components/Loading.jsx';
import {
  changeApplicationStatus,
  createApplication,
  deleteApplication,
  getApplication,
  getVacancies,
  listApplicationHistory,
  listApplications,
  listCoverLetterVersions,
  listResumeVersions,
  updateApplication,
} from '../api/endpoints.js';
import { formatDateTime } from '../utils/formatters.js';
import { useAuth } from '../auth/useAuth.js';
import PageHeader from '../components/ui/PageHeader.jsx';
import SectionCard from '../components/ui/SectionCard.jsx';

const STATUSES = [
  'saved',
  'planned',
  'applied',
  'hr_screen',
  'tech_interview',
  'test_task',
  'offer',
  'rejected',
  'archived',
];

const STATUS_META = {
  saved: { label: 'Сохранено', tone: 'neutral' },
  planned: { label: 'Запланировано', tone: 'info' },
  applied: { label: 'Отклик отправлен', tone: 'info' },
  hr_screen: { label: 'Скрининг HR', tone: 'info' },
  tech_interview: { label: 'Техническое интервью', tone: 'accent' },
  test_task: { label: 'Тестовое задание', tone: 'accent' },
  offer: { label: 'Оффер', tone: 'success' },
  rejected: { label: 'Отказ', tone: 'danger' },
  archived: { label: 'В архиве', tone: 'muted' },
};

const ACTIVE_EXCLUDED_STATUSES = new Set(['rejected', 'archived']);
const INTERVIEW_STATUSES = new Set(['hr_screen', 'tech_interview', 'test_task']);

function groupByStatus(items) {
  const grouped = Object.fromEntries(STATUSES.map((status) => [status, []]));
  items.forEach((item) => {
    if (!grouped[item.status]) {
      grouped[item.status] = [];
    }
    grouped[item.status].push(item);
  });
  return grouped;
}

function getNotePreview(note) {
  if (!note) {
    return 'Пока нет заметок';
  }
  if (note.length <= 100) {
    return note;
  }
  return `${note.slice(0, 100)}…`;
}

function getStatusMeta(status) {
  return STATUS_META[status] || { label: status, tone: 'neutral' };
}

function getExternalApplyStatusLabel(status) {
  if (!status) {
    return '—';
  }
  if (status === 'already_applied') {
    return 'already_applied (на HH уже был отклик)';
  }
  if (status === 'отправлено') {
    return 'отправлено';
  }
  return status;
}

export default function ApplicationsPage() {
  const { profileId } = useAuth();
  const [applications, setApplications] = useState([]);
  const [vacancies, setVacancies] = useState([]);
  const [resumeVersions, setResumeVersions] = useState([]);
  const [coverLetters, setCoverLetters] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [selectedVacancyId, setSelectedVacancyId] = useState('');
  const [createError, setCreateError] = useState('');
  const [createSuccess, setCreateSuccess] = useState('');
  const [selectedApplicationId, setSelectedApplicationId] = useState(null);
  const [selectedApplication, setSelectedApplication] = useState(null);
  const [historyByApplicationId, setHistoryByApplicationId] = useState({});
  const [historyLoadingIds, setHistoryLoadingIds] = useState([]);
  const [detailsLoading, setDetailsLoading] = useState(false);
  const [editForm, setEditForm] = useState({ note: '', resume_version_id: '', cover_letter_version_id: '' });
  const [statusFilter, setStatusFilter] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [hideArchived, setHideArchived] = useState(true);
  const [sortOrder, setSortOrder] = useState('updated_desc');

  const loadAll = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [applicationsResponse, vacanciesResponse, resumeResponse, coverResponse] = await Promise.all([
        listApplications(profileId),
        getVacancies(),
        listResumeVersions(profileId),
        listCoverLetterVersions(profileId),
      ]);
      setApplications(applicationsResponse);
      setVacancies(vacanciesResponse);
      setResumeVersions(resumeResponse);
      setCoverLetters(coverResponse);
    } catch (requestError) {
      setError(requestError.message || 'Не удалось загрузить отклики');
    } finally {
      setLoading(false);
    }
  }, [profileId]);

  const vacancyMap = useMemo(() => new Map(vacancies.map((vacancy) => [vacancy.id, vacancy])), [vacancies]);
  const resumeMap = useMemo(() => new Map(resumeVersions.map((item) => [item.id, item])), [resumeVersions]);
  const coverMap = useMemo(() => new Map(coverLetters.map((item) => [item.id, item])), [coverLetters]);

  const summary = useMemo(() => ({
    total: applications.length,
    active: applications.filter((item) => !ACTIVE_EXCLUDED_STATUSES.has(item.status)).length,
    applied: applications.filter((item) => item.status === 'applied').length,
    interview: applications.filter((item) => INTERVIEW_STATUSES.has(item.status)).length,
    offers: applications.filter((item) => item.status === 'offer').length,
  }), [applications]);

  const filteredApplications = useMemo(() => {
    const normalizedQuery = searchQuery.trim().toLowerCase();

    return applications
      .filter((item) => (statusFilter === 'all' ? true : item.status === statusFilter))
      .filter((item) => (hideArchived ? item.status !== 'archived' : true))
      .filter((item) => {
        if (!normalizedQuery) {
          return true;
        }
        const vacancy = vacancyMap.get(item.vacancy_id);
        const title = vacancy?.title || '';
        const company = vacancy?.company_name || '';
        return `${title} ${company}`.toLowerCase().includes(normalizedQuery);
      })
      .sort((left, right) => {
        const leftTs = new Date(left.updated_at).getTime();
        const rightTs = new Date(right.updated_at).getTime();
        if (sortOrder === 'updated_asc') {
          return leftTs - rightTs;
        }
        return rightTs - leftTs;
      });
  }, [applications, hideArchived, searchQuery, sortOrder, statusFilter, vacancyMap]);

  const grouped = useMemo(() => groupByStatus(filteredApplications), [filteredApplications]);

  const ensureHistoryLoaded = useCallback(async (applicationId) => {
    if (historyByApplicationId[applicationId]) {
      return historyByApplicationId[applicationId];
    }

    setHistoryLoadingIds((current) => [...current, applicationId]);
    try {
      const history = await listApplicationHistory(profileId, applicationId);
      setHistoryByApplicationId((current) => ({ ...current, [applicationId]: history }));
      return history;
    } catch (requestError) {
      setError(requestError.message || 'Не удалось загрузить историю статусов');
      return [];
    } finally {
      setHistoryLoadingIds((current) => current.filter((id) => id !== applicationId));
    }
  }, [historyByApplicationId, profileId]);

  const refreshHistory = useCallback(async (applicationId) => {
    try {
      const history = await listApplicationHistory(profileId, applicationId);
      setHistoryByApplicationId((current) => ({ ...current, [applicationId]: history }));
    } catch (requestError) {
      setError(requestError.message || 'Не удалось обновить историю статусов');
    }
  }, [profileId]);

  const openDetails = useCallback(async (applicationId) => {
    setDetailsLoading(true);
    setSelectedApplicationId(applicationId);
    try {
      const application = await getApplication(profileId, applicationId);
      setSelectedApplication(application);
      setEditForm({
        note: application.note ?? '',
        resume_version_id: application.resume_version_id ? String(application.resume_version_id) : '',
        cover_letter_version_id: application.cover_letter_version_id ? String(application.cover_letter_version_id) : '',
      });
      await ensureHistoryLoaded(applicationId);
    } catch (requestError) {
      setError(requestError.message || 'Не удалось загрузить детали отклика');
    } finally {
      setDetailsLoading(false);
    }
  }, [ensureHistoryLoaded, profileId]);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  const handleCreate = async () => {
    if (!selectedVacancyId) {
      return;
    }
    setCreateError('');
    setCreateSuccess('');
    try {
      const created = await createApplication(profileId, { vacancy_id: Number(selectedVacancyId) });
      setApplications((current) => [created, ...current]);
      setCreateSuccess('Отклик добавлен в воронку.');
      setSelectedVacancyId('');
      setSelectedApplicationId(created.id);
      await openDetails(created.id);
    } catch (requestError) {
      setCreateError(requestError.message || 'Не удалось создать отклик');
    }
  };

  const handleStatusQuickChange = async (applicationId, statusValue) => {
    try {
      const updated = await changeApplicationStatus(profileId, applicationId, { status: statusValue });
      setApplications((current) => current.map((item) => (item.id === updated.id ? updated : item)));
      if (selectedApplicationId === applicationId) {
        setSelectedApplication(updated);
      }
      await refreshHistory(applicationId);
    } catch (requestError) {
      setError(requestError.message || 'Не удалось изменить статус');
    }
  };

  const handleSaveDetails = async () => {
    if (!selectedApplicationId) {
      return;
    }

    try {
      const updated = await updateApplication(profileId, selectedApplicationId, {
        note: editForm.note || null,
        resume_version_id: editForm.resume_version_id ? Number(editForm.resume_version_id) : null,
        cover_letter_version_id: editForm.cover_letter_version_id ? Number(editForm.cover_letter_version_id) : null,
      });
      setApplications((current) => current.map((item) => (item.id === updated.id ? updated : item)));
      setSelectedApplication(updated);
      await refreshHistory(selectedApplicationId);
    } catch (requestError) {
      setError(requestError.message || 'Не удалось сохранить отклик');
    }
  };

  const handleDelete = async (applicationId) => {
    try {
      await deleteApplication(profileId, applicationId);
      setApplications((current) => current.filter((item) => item.id !== applicationId));
      if (selectedApplicationId === applicationId) {
        setSelectedApplicationId(null);
        setSelectedApplication(null);
      }
    } catch (requestError) {
      setError(requestError.message || 'Не удалось удалить отклик');
    }
  };

  if (loading) {
    return <Loading message="Загружаем отклики..." />;
  }

  const selectedHistory = selectedApplicationId ? historyByApplicationId[selectedApplicationId] || [] : [];
  const selectedResume = selectedApplication?.resume_version_id
    ? resumeMap.get(selectedApplication.resume_version_id)
    : null;
  const selectedCover = selectedApplication?.cover_letter_version_id
    ? coverMap.get(selectedApplication.cover_letter_version_id)
    : null;

  return (
    <section className="page-stack applications-page">
      <PageHeader
        eyebrow=""
        title="Воронка откликов"
        subtitle="Компактная доска по статусам, быстрые правки и связка с документами."
      />
      {error ? <ErrorBanner message={error} /> : null}

      <section className="applications-summary" aria-label="Сводка по откликам">
        <article><p>Всего</p><strong>{summary.total}</strong></article>
        <article><p>Активные</p><strong>{summary.active}</strong></article>
        <article><p>Applied</p><strong>{summary.applied}</strong></article>
        <article><p>Interview</p><strong>{summary.interview}</strong></article>
        <article><p>Offers</p><strong>{summary.offers}</strong></article>
      </section>

      <SectionCard title="Создать отклик" subtitle="Добавьте вакансию в воронку и сразу откройте детали.">
        <div className="applications-create-row">
          <select value={selectedVacancyId} onChange={(event) => setSelectedVacancyId(event.target.value)}>
            <option value="">Выберите вакансию</option>
            {vacancies.map((vacancy) => (
              <option key={vacancy.id} value={vacancy.id}>
                {vacancy.title} — {vacancy.company_name || 'Неизвестная компания'}
              </option>
            ))}
          </select>
          <button className="button" type="button" onClick={handleCreate}>Добавить в воронку</button>
        </div>
        {createSuccess ? <p className="vacancy-details__docgen-success">{createSuccess}</p> : null}
        {createError ? <ErrorBanner message={createError} /> : null}
      </SectionCard>

      <SectionCard title="Фильтры" subtitle="Сузьте доску по статусу, тексту и дате обновления.">
        <div className="applications-filters">
          <label>
            Поиск
            <input type="search" value={searchQuery} onChange={(event) => setSearchQuery(event.target.value)} placeholder="вакансия или компания" />
          </label>
          <label>
            Status
            <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
              <option value="all">Все статусы</option>
              {STATUSES.map((statusValue) => (
                <option key={statusValue} value={statusValue}>{getStatusMeta(statusValue).label}</option>
              ))}
            </select>
          </label>
          <label>
            Сортировка
            <select value={sortOrder} onChange={(event) => setSortOrder(event.target.value)}>
              <option value="updated_desc">Сначала новые</option>
              <option value="updated_asc">Сначала старые</option>
            </select>
          </label>
          <label className="applications-filters__checkbox">
            <input type="checkbox" checked={hideArchived} onChange={(event) => setHideArchived(event.target.checked)} />
            Скрывать archived
          </label>
        </div>
      </SectionCard>

      <div className="applications-board">
        {STATUSES.map((status) => {
          const items = grouped[status] || [];
          const statusMeta = getStatusMeta(status);
          return (
            <article className="applications-column" key={status}>
              <h3>
                <span className={`applications-status-chip applications-status-chip--${statusMeta.tone}`}>{statusMeta.label}</span>
                <span>{items.length}</span>
              </h3>
              <div className="applications-column__items">
                {items.length === 0 ? <p className="applications-column__empty">Нет откликов</p> : null}
                {items.map((application) => {
                  const vacancy = vacancyMap.get(application.vacancy_id);
                  const resume = application.resume_version_id ? resumeMap.get(application.resume_version_id) : null;
                  const cover = application.cover_letter_version_id ? coverMap.get(application.cover_letter_version_id) : null;
                  const history = historyByApplicationId[application.id] || [];
                  const isHistoryLoading = historyLoadingIds.includes(application.id);
                  const appStatusMeta = getStatusMeta(application.status);

                  return (
                    <div className="applications-card" key={application.id}>
                      <p className="applications-card__title"><strong>{vacancy?.title ?? `Вакансия #${application.vacancy_id}`}</strong></p>
                      <p className="applications-card__company">{vacancy?.company_name || 'Неизвестная компания'}</p>
                      {application.last_hh_apply_run_id ? (
                        <div className="applications-card__source-row">
                          <span className="applications-source-badge">HH sync</span>
                          {application.external_apply_status ? (
                            <span className="muted-text">external: {getExternalApplyStatusLabel(application.external_apply_status)}</span>
                          ) : null}
                        </div>
                      ) : null}
                      <div className="applications-card__meta-row">
                        <span className={`applications-status-chip applications-status-chip--${appStatusMeta.tone}`}>{appStatusMeta.label}</span>
                        <span className="muted-text">{formatDateTime(application.updated_at) ?? '—'}</span>
                      </div>
                      <p className="applications-card__note">{getNotePreview(application.note)}</p>

                      <div className="applications-card__docs">
                        <p>Resume: {resume?.title || 'Не привязано'} {resume?.status === 'approved' ? <span className="doc-state-badge doc-state-badge--approved">approved</span> : null}</p>
                        <p>Cover letter: {cover?.title || 'Не привязано'} {cover?.status === 'approved' ? <span className="doc-state-badge doc-state-badge--approved">approved</span> : null}</p>
                        {application.last_hh_apply_run_id ? <p>HH apply run: #{application.last_hh_apply_run_id}</p> : null}
                        {application.hh_managed_resume_id ? <p>HH resume id: #{application.hh_managed_resume_id}</p> : null}
                        {application.last_external_apply_at ? <p>HH applied at: {formatDateTime(application.last_external_apply_at) ?? '—'}</p> : null}
                      </div>

                      <div className="applications-card__actions">
                        <select value={application.status} onChange={(event) => handleStatusQuickChange(application.id, event.target.value)}>
                          {STATUSES.map((statusValue) => (
                            <option key={statusValue} value={statusValue}>{getStatusMeta(statusValue).label}</option>
                          ))}
                        </select>
                        <button type="button" onClick={() => openDetails(application.id)}>Детали</button>
                        <Link to={`/vacancies/${application.vacancy_id}`}>Вакансия</Link>
                        <button type="button" className="button--danger" onClick={() => handleDelete(application.id)}>Удалить</button>
                      </div>

                      <details className="applications-card__history" onToggle={(event) => {
                        if (event.currentTarget.open) {
                          ensureHistoryLoaded(application.id);
                        }
                      }}>
                        <summary>История статусов</summary>
                        {isHistoryLoading ? <p>Загружаем историю...</p> : null}
                        {history.length === 0 ? <p>Пока нет событий истории.</p> : null}
                        <ul className="history-timeline">
                          {history.map((item) => (
                            <li key={item.id}>
                              <span>{formatDateTime(item.created_at) ?? '—'}</span>
                              <span>{getStatusMeta(item.from_status || 'saved').label} → {getStatusMeta(item.to_status).label}</span>
                              <span>{item.note || 'без заметки'}{item.hh_apply_run_id ? ` · HH apply run #${item.hh_apply_run_id}` : ''}</span>
                            </li>
                          ))}
                        </ul>
                      </details>
                    </div>
                  );
                })}
              </div>
            </article>
          );
        })}
      </div>

      {selectedApplicationId ? (
        <article className="vacancy-details applications-detail-panel">
          <h2 className="vacancy-details__section-title">Детали отклика #{selectedApplicationId}</h2>
          {detailsLoading ? <Loading message="Загружаем детали..." /> : null}
          {selectedApplication ? (
            <>
              <div className="applications-status-quickbar">
                {STATUSES.map((statusValue) => (
                  <button
                    key={statusValue}
                    type="button"
                    className={statusValue === selectedApplication.status ? 'applications-status-quickbar__active' : ''}
                    onClick={() => handleStatusQuickChange(selectedApplication.id, statusValue)}
                  >
                    {getStatusMeta(statusValue).label}
                  </button>
                ))}
              </div>
              <label>
                Note
                <textarea value={editForm.note} onChange={(event) => setEditForm((current) => ({ ...current, note: event.target.value }))} rows={4} />
              </label>
              <div className="settings-grid settings-grid--two">
                <label>
                  Resume version
                  <select value={editForm.resume_version_id} onChange={(event) => setEditForm((current) => ({ ...current, resume_version_id: event.target.value }))}>
                    <option value="">Not linked</option>
                    {resumeVersions
                      .filter((item) => item.vacancy_id == null || item.vacancy_id === selectedApplication.vacancy_id)
                      .map((item) => (
                        <option key={item.id} value={item.id}>
                          {(item.title || `Резюме #${item.id}`)}{item.status === 'approved' ? ' • approved' : ''}
                        </option>
                      ))}
                  </select>
                </label>
                <label>
                  Cover letter version
                  <select value={editForm.cover_letter_version_id} onChange={(event) => setEditForm((current) => ({ ...current, cover_letter_version_id: event.target.value }))}>
                    <option value="">Not linked</option>
                    {coverLetters
                      .filter((item) => item.vacancy_id == null || item.vacancy_id === selectedApplication.vacancy_id)
                      .map((item) => (
                        <option key={item.id} value={item.id}>
                          {(item.title || `Сопроводительное письмо #${item.id}`)}{item.status === 'approved' ? ' • approved' : ''}
                        </option>
                      ))}
                  </select>
                </label>
              </div>
              <button className="button" type="button" onClick={handleSaveDetails}>Save changes</button>

              <h3 className="vacancy-details__section-title">Связанные документы</h3>
              <ul>
                <li>Resume: {selectedResume ? <>{selectedResume.title || `Резюме #${selectedResume.id}`} ({selectedResume.status}) · <Link to="/settings">открыть в настройках</Link></> : 'Пока не прикреплено'}</li>
                <li>Cover letter: {selectedCover ? <>{selectedCover.title || `Сопроводительное письмо #${selectedCover.id}`} ({selectedCover.status}) · <Link to="/settings">открыть в настройках</Link></> : 'Пока не прикреплено'}</li>
              </ul>

              {selectedApplication.last_hh_apply_run_id ? (
                <>
                  <h3 className="vacancy-details__section-title">HH automation linkage</h3>
                  <ul>
                    <li>Источник: HH apply automation (run #{selectedApplication.last_hh_apply_run_id})</li>
                    <li>External apply status: {getExternalApplyStatusLabel(selectedApplication.external_apply_status)}</li>
                    <li>HH managed resume id: {selectedApplication.hh_managed_resume_id ? `#${selectedApplication.hh_managed_resume_id}` : 'не зафиксирован'}</li>
                    <li>Последний external apply: {formatDateTime(selectedApplication.last_external_apply_at) ?? '—'}</li>
                  </ul>
                </>
              ) : null}

              <h3 className="vacancy-details__section-title">История статусов</h3>
              <ul className="history-timeline history-timeline--panel">
                {selectedHistory.map((item) => (
                  <li key={item.id}>
                    <span>{formatDateTime(item.created_at) ?? '—'}</span>
                    <span>{getStatusMeta(item.from_status || 'saved').label} → {getStatusMeta(item.to_status).label}</span>
                    <span>{item.note || 'без заметки'}{item.hh_apply_run_id ? ` · HH apply run #${item.hh_apply_run_id}` : ''}</span>
                  </li>
                ))}
              </ul>
            </>
          ) : null}
        </article>
      ) : null}
    </section>
  );
}
