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
  const [historyItems, setHistoryItems] = useState([]);
  const [detailsLoading, setDetailsLoading] = useState(false);
  const [editForm, setEditForm] = useState({ note: '', resume_version_id: '', cover_letter_version_id: '' });

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
  const grouped = useMemo(() => groupByStatus(applications), [applications]);

  const openDetails = useCallback(async (applicationId) => {
    setDetailsLoading(true);
    setSelectedApplicationId(applicationId);
    try {
      const [application, history] = await Promise.all([
        getApplication(DEFAULT_PROFILE_ID, applicationId),
        listApplicationHistory(DEFAULT_PROFILE_ID, applicationId),
      ]);
      setSelectedApplication(application);
      setEditForm({
        note: application.note ?? '',
        resume_version_id: application.resume_version_id ? String(application.resume_version_id) : '',
        cover_letter_version_id: application.cover_letter_version_id ? String(application.cover_letter_version_id) : '',
      });
      setHistoryItems(history);
    } catch (requestError) {
      setError(requestError.message || 'Failed to load application details');
    } finally {
      setDetailsLoading(false);
    }
  }, []);

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
        await openDetails(applicationId);
      }
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
      await openDetails(selectedApplicationId);
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
        setHistoryItems([]);
      }
    } catch (requestError) {
      setError(requestError.message || 'Failed to delete application');
    }
  };

  if (loading) {
    return <Loading text="Loading applications..." />;
  }

  return (
    <section className="page-stack">
      <h1>Applications funnel</h1>
      {error ? <ErrorBanner message={error} /> : null}

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

      <div className="applications-board">
        {STATUSES.map((status) => (
          <article className="applications-column" key={status}>
            <h3>{status}</h3>
            <div className="applications-column__items">
              {(grouped[status] || []).map((application) => {
                const vacancy = vacancyMap.get(application.vacancy_id);
                const resume = application.resume_version_id ? resumeMap.get(application.resume_version_id) : null;
                const cover = application.cover_letter_version_id ? coverMap.get(application.cover_letter_version_id) : null;
                return (
                  <div className="applications-card" key={application.id}>
                    <p><strong>{vacancy?.title ?? `Vacancy #${application.vacancy_id}`}</strong></p>
                    <p>{vacancy?.company_name || 'Unknown company'}</p>
                    <p>Updated: {formatDateTime(application.updated_at) ?? '—'}</p>
                    <p>Resume: {resume?.title || '—'}</p>
                    <p>Cover letter: {cover?.title || '—'}</p>
                    <p>Note: {application.note || '—'}</p>
                    <div className="applications-card__actions">
                      <select
                        value={application.status}
                        onChange={(event) => handleStatusQuickChange(application.id, event.target.value)}
                      >
                        {STATUSES.map((statusValue) => (
                          <option key={statusValue} value={statusValue}>{statusValue}</option>
                        ))}
                      </select>
                      <button type="button" onClick={() => openDetails(application.id)}>Edit</button>
                      <button type="button" onClick={() => handleDelete(application.id)}>Delete</button>
                      <Link to={`/vacancies/${application.vacancy_id}`}>Vacancy</Link>
                    </div>
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
              <label>
                Status
                <select
                  value={selectedApplication.status}
                  onChange={(event) => handleStatusQuickChange(selectedApplication.id, event.target.value)}
                >
                  {STATUSES.map((statusValue) => (
                    <option key={statusValue} value={statusValue}>{statusValue}</option>
                  ))}
                </select>
              </label>
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
                      <option key={item.id} value={item.id}>{item.title || `Resume #${item.id}`}</option>
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
                      <option key={item.id} value={item.id}>{item.title || `Cover letter #${item.id}`}</option>
                    ))}
                </select>
              </label>
              <button className="recommendations-toolbar__button" type="button" onClick={handleSaveDetails}>Save changes</button>

              <h3 className="vacancy-details__section-title">Status history</h3>
              <ul>
                {historyItems.map((item) => (
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
