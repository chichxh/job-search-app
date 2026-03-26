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
import { DEFAULT_PROFILE_ID } from '../config.js';
import { formatDateTime } from '../utils/formatters.js';

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
    return '—';
  }
  if (note.length <= 90) {
    return note;
  }
  return `${note.slice(0, 90)}…`;
}

export default function ApplicationsPage() {
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
        listApplications(DEFAULT_PROFILE_ID),
        getVacancies(),
        listResumeVersions(DEFAULT_PROFILE_ID),
        listCoverLetterVersions(DEFAULT_PROFILE_ID),
      ]);
      setApplications(applicationsResponse);
      setVacancies(vacanciesResponse);
      setResumeVersions(resumeResponse);
      setCoverLetters(coverResponse);
    } catch (requestError) {
      setError(requestError.message || 'Failed to load applications');
    } finally {
      setLoading(false);
    }
  }, []);

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
      const history = await listApplicationHistory(DEFAULT_PROFILE_ID, applicationId);
      setHistoryByApplicationId((current) => ({ ...current, [applicationId]: history }));
      return history;
    } catch (requestError) {
      setError(requestError.message || 'Failed to load status history');
      return [];
    } finally {
      setHistoryLoadingIds((current) => current.filter((id) => id !== applicationId));
    }
  }, [historyByApplicationId]);

  const refreshHistory = useCallback(async (applicationId) => {
    try {
      const history = await listApplicationHistory(DEFAULT_PROFILE_ID, applicationId);
      setHistoryByApplicationId((current) => ({ ...current, [applicationId]: history }));
    } catch (requestError) {
      setError(requestError.message || 'Failed to refresh status history');
    }
  }, []);

  const openDetails = useCallback(async (applicationId) => {
    setDetailsLoading(true);
    setSelectedApplicationId(applicationId);
    try {
      const application = await getApplication(DEFAULT_PROFILE_ID, applicationId);
      setSelectedApplication(application);
      setEditForm({
        note: application.note ?? '',
        resume_version_id: application.resume_version_id ? String(application.resume_version_id) : '',
        cover_letter_version_id: application.cover_letter_version_id ? String(application.cover_letter_version_id) : '',
      });
      await ensureHistoryLoaded(applicationId);
    } catch (requestError) {
      setError(requestError.message || 'Failed to load application details');
    } finally {
      setDetailsLoading(false);
    }
  }, [ensureHistoryLoaded]);

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
      const created = await createApplication(DEFAULT_PROFILE_ID, { vacancy_id: Number(selectedVacancyId) });
      setApplications((current) => [created, ...current]);
      setCreateSuccess('Application added to funnel.');
      setSelectedVacancyId('');
      setSelectedApplicationId(created.id);
      await openDetails(created.id);
    } catch (requestError) {
      setCreateError(requestError.message || 'Failed to create application');
    }
  };

  const handleStatusQuickChange = async (applicationId, statusValue) => {
    try {
      const updated = await changeApplicationStatus(DEFAULT_PROFILE_ID, applicationId, { status: statusValue });
      setApplications((current) => current.map((item) => (item.id === updated.id ? updated : item)));
      if (selectedApplicationId === applicationId) {
        setSelectedApplication(updated);
      }
      await refreshHistory(applicationId);
    } catch (requestError) {
      setError(requestError.message || 'Failed to change status');
    }
  };

  const handleSaveDetails = async () => {
    if (!selectedApplicationId) {
      return;
    }

    try {
      const updated = await updateApplication(DEFAULT_PROFILE_ID, selectedApplicationId, {
        note: editForm.note || null,
        resume_version_id: editForm.resume_version_id ? Number(editForm.resume_version_id) : null,
        cover_letter_version_id: editForm.cover_letter_version_id ? Number(editForm.cover_letter_version_id) : null,
      });
      setApplications((current) => current.map((item) => (item.id === updated.id ? updated : item)));
      setSelectedApplication(updated);
      await refreshHistory(selectedApplicationId);
    } catch (requestError) {
      setError(requestError.message || 'Failed to save application');
    }
  };

  const handleDelete = async (applicationId) => {
    try {
      await deleteApplication(DEFAULT_PROFILE_ID, applicationId);
      setApplications((current) => current.filter((item) => item.id !== applicationId));
      if (selectedApplicationId === applicationId) {
        setSelectedApplicationId(null);
        setSelectedApplication(null);
      }
    } catch (requestError) {
      setError(requestError.message || 'Failed to delete application');
    }
  };

  if (loading) {
    return <Loading text="Loading applications..." />;
  }

  const selectedHistory = selectedApplicationId ? historyByApplicationId[selectedApplicationId] || [] : [];
  const selectedResume = selectedApplication?.resume_version_id
    ? resumeMap.get(selectedApplication.resume_version_id)
    : null;
  const selectedCover = selectedApplication?.cover_letter_version_id
    ? coverMap.get(selectedApplication.cover_letter_version_id)
    : null;

  return (
    <section className="page-stack">
      <h1>Applications funnel</h1>
      {error ? <ErrorBanner message={error} /> : null}

      <section className="applications-summary" aria-label="Applications summary">
        <article>
          <p>Total applications</p>
          <strong>{summary.total}</strong>
        </article>
        <article>
          <p>Active</p>
          <strong>{summary.active}</strong>
        </article>
        <article>
          <p>Applied</p>
          <strong>{summary.applied}</strong>
        </article>
        <article>
          <p>Interview stage</p>
          <strong>{summary.interview}</strong>
        </article>
        <article>
          <p>Offers</p>
          <strong>{summary.offers}</strong>
        </article>
      </section>

      <article className="vacancy-details">
        <h2 className="vacancy-details__section-title">Create from vacancy</h2>
        <div className="applications-create-row">
          <select value={selectedVacancyId} onChange={(event) => setSelectedVacancyId(event.target.value)}>
            <option value="">Select vacancy</option>
            {vacancies.map((vacancy) => (
              <option key={vacancy.id} value={vacancy.id}>
                {vacancy.title} — {vacancy.company_name || 'Unknown company'}
              </option>
            ))}
          </select>
          <button className="recommendations-toolbar__button" type="button" onClick={handleCreate}>Add to applications</button>
        </div>
        {createSuccess ? <p className="vacancy-details__docgen-success">{createSuccess}</p> : null}
        {createError ? <ErrorBanner message={createError} /> : null}
      </article>

      <article className="vacancy-details">
        <h2 className="vacancy-details__section-title">Filters & sorting</h2>
        <div className="applications-filters">
          <label>
            Search vacancy / company
            <input
              type="search"
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
              placeholder="e.g. Frontend, Acme"
            />
          </label>
          <label>
            Status
            <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
              <option value="all">All statuses</option>
              {STATUSES.map((statusValue) => (
                <option key={statusValue} value={statusValue}>{statusValue}</option>
              ))}
            </select>
          </label>
          <label>
            Sort by updated
            <select value={sortOrder} onChange={(event) => setSortOrder(event.target.value)}>
              <option value="updated_desc">Newest first</option>
              <option value="updated_asc">Oldest first</option>
            </select>
          </label>
          <label className="applications-filters__checkbox">
            <input
              type="checkbox"
              checked={hideArchived}
              onChange={(event) => setHideArchived(event.target.checked)}
            />
            Hide archived
          </label>
        </div>
      </article>

      <div className="applications-board">
        {STATUSES.map((status) => (
          <article className="applications-column" key={status}>
            <h3>
              {status}
              <span>{(grouped[status] || []).length}</span>
            </h3>
            <div className="applications-column__items">
              {(grouped[status] || []).length === 0 ? <p className="applications-column__empty">No applications</p> : null}
              {(grouped[status] || []).map((application) => {
                const vacancy = vacancyMap.get(application.vacancy_id);
                const resume = application.resume_version_id ? resumeMap.get(application.resume_version_id) : null;
                const cover = application.cover_letter_version_id ? coverMap.get(application.cover_letter_version_id) : null;
                const history = historyByApplicationId[application.id] || [];
                const isHistoryLoading = historyLoadingIds.includes(application.id);

                return (
                  <div className="applications-card" key={application.id}>
                    <p className="applications-card__title"><strong>{vacancy?.title ?? `Vacancy #${application.vacancy_id}`}</strong></p>
                    <p>{vacancy?.company_name || 'Unknown company'}</p>
                    <p>Status: <span className="applications-card__status">{application.status}</span></p>
                    <p>Updated: {formatDateTime(application.updated_at) ?? '—'}</p>
                    <p>Note: {getNotePreview(application.note)}</p>
                    <p>
                      Resume: {resume?.title || 'Not linked'}
                      {resume?.status === 'approved' ? <span className="applications-card__approved">Approved</span> : null}
                    </p>
                    <p>
                      Cover letter: {cover?.title || 'Not linked'}
                      {cover?.status === 'approved' ? <span className="applications-card__approved">Approved</span> : null}
                    </p>
                    <div className="applications-card__actions">
                      <select
                        value={application.status}
                        onChange={(event) => handleStatusQuickChange(application.id, event.target.value)}
                      >
                        {STATUSES.map((statusValue) => (
                          <option key={statusValue} value={statusValue}>{statusValue}</option>
                        ))}
                      </select>
                      <button type="button" onClick={() => openDetails(application.id)}>Details</button>
                      <button type="button" onClick={() => handleDelete(application.id)}>Delete</button>
                      <Link to={`/vacancies/${application.vacancy_id}`}>Vacancy</Link>
                    </div>
                    <details className="applications-card__history" onToggle={(event) => {
                      if (event.currentTarget.open) {
                        ensureHistoryLoaded(application.id);
                      }
                    }}>
                      <summary>Status history</summary>
                      {isHistoryLoading ? <p>Loading history...</p> : null}
                      {history.length === 0 ? <p>No history events yet.</p> : null}
                      {history.map((item) => (
                        <p key={item.id}>
                          {formatDateTime(item.created_at) ?? '—'}: {item.from_status || '—'} → {item.to_status} ({item.note || 'no note'})
                        </p>
                      ))}
                    </details>
                  </div>
                );
              })}
            </div>
          </article>
        ))}
      </div>

      {selectedApplicationId ? (
        <article className="vacancy-details">
          <h2 className="vacancy-details__section-title">Application details #{selectedApplicationId}</h2>
          {detailsLoading ? <Loading text="Loading details..." /> : null}
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
                    {statusValue}
                  </button>
                ))}
              </div>
              <label>
                Note
                <textarea
                  value={editForm.note}
                  onChange={(event) => setEditForm((current) => ({ ...current, note: event.target.value }))}
                  rows={3}
                />
              </label>
              <label>
                Resume version
                <select
                  value={editForm.resume_version_id}
                  onChange={(event) => setEditForm((current) => ({ ...current, resume_version_id: event.target.value }))}
                >
                  <option value="">Not linked</option>
                  {resumeVersions
                    .filter((item) => item.vacancy_id == null || item.vacancy_id === selectedApplication.vacancy_id)
                    .map((item) => (
                      <option key={item.id} value={item.id}>
                        {(item.title || `Resume #${item.id}`)}{item.status === 'approved' ? ' • approved' : ''}
                      </option>
                    ))}
                </select>
              </label>
              <label>
                Cover letter version
                <select
                  value={editForm.cover_letter_version_id}
                  onChange={(event) => setEditForm((current) => ({ ...current, cover_letter_version_id: event.target.value }))}
                >
                  <option value="">Not linked</option>
                  {coverLetters
                    .filter((item) => item.vacancy_id == null || item.vacancy_id === selectedApplication.vacancy_id)
                    .map((item) => (
                      <option key={item.id} value={item.id}>
                        {(item.title || `Cover letter #${item.id}`)}{item.status === 'approved' ? ' • approved' : ''}
                      </option>
                    ))}
                </select>
              </label>
              <button className="recommendations-toolbar__button" type="button" onClick={handleSaveDetails}>Save changes</button>

              <h3 className="vacancy-details__section-title">Linked documents</h3>
              <ul>
                <li>
                  Resume:{' '}
                  {selectedResume ? (
                    <>
                      {selectedResume.title || `Resume #${selectedResume.id}`} ({selectedResume.status}) · <Link to="/settings">open in Settings</Link>
                    </>
                  ) : (
                    'Not attached yet'
                  )}
                </li>
                <li>
                  Cover letter:{' '}
                  {selectedCover ? (
                    <>
                      {selectedCover.title || `Cover letter #${selectedCover.id}`} ({selectedCover.status}) · <Link to="/settings">open in Settings</Link>
                    </>
                  ) : (
                    'Not attached yet'
                  )}
                </li>
              </ul>

              <h3 className="vacancy-details__section-title">Status history</h3>
              <ul>
                {selectedHistory.map((item) => (
                  <li key={item.id}>
                    {formatDateTime(item.created_at) ?? '—'}: {item.from_status || '—'} → {item.to_status} ({item.note || 'no note'})
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
