import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useParams } from 'react-router-dom';

import {
  approveCoverLetterVersion,
  approveResumeVersion,
  generateCoverLetterDraft,
  generateResumeDraft,
  getTailoring,
  getVacancyById,
  listCoverLetterVersions,
  listResumeVersions,
  updateCoverLetterVersion,
  updateResumeVersion,
} from '../api/endpoints.js';
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

function toPreviewText(value, maxLength = 280) {
  if (!value) {
    return '—';
  }

  const text = String(value).trim();
  if (text.length <= maxLength) {
    return text;
  }

  return `${text.slice(0, maxLength)}…`;
}

function getUserFacingError(error, fallback) {
  const rawMessage = String(error?.message ?? '').trim();
  if (!rawMessage) {
    return fallback;
  }

  const detailMatch = rawMessage.match(/\):\s*(.+)$/);
  if (detailMatch?.[1]) {
    return detailMatch[1].trim();
  }

  return rawMessage;
}

function getDocumentTypeLabel(type) {
  return type === 'resume' ? 'Resume' : 'Cover letter';
}

function getMetadataEntries(metadata) {
  if (!metadata || typeof metadata !== 'object') {
    return [];
  }

  return Object.entries(metadata).filter(([, value]) => value !== null && value !== undefined && value !== '');
}

function renderMetadataCompact(metadata) {
  const metadataEntries = getMetadataEntries(metadata);
  if (!metadataEntries.length) {
    return 'No generation metadata';
  }

  const compactKeys = ['provider', 'model', 'prompt_version', 'generated_at'];
  const compactEntries = compactKeys
    .map((key) => [key, metadata[key]])
    .filter(([, value]) => value !== null && value !== undefined && value !== '');

  if (!compactEntries.length) {
    return `${metadataEntries.length} fields available`;
  }

  return compactEntries
    .map(([key, value]) => {
      if (key === 'generated_at') {
        return `${key}: ${formatDateTime(value) ?? value}`;
      }
      return `${key}: ${value}`;
    })
    .join(' · ');
}

function GenerationResultBlock({ result, onRegenerate }) {
  if (!result?.document) {
    return null;
  }

  const { type, document } = result;
  const metadataEntries = getMetadataEntries(document.generation_metadata);

  return (
    <article className="vacancy-details__created-draft" aria-live="polite">
      <h3 className="vacancy-details__section-title">Created draft ({getDocumentTypeLabel(type)})</h3>
      <p><strong>title:</strong> {getSafeText(document.title, '—')}</p>
      <p><strong>status:</strong> {getSafeText(document.status, '—')}</p>
      <p><strong>created_at:</strong> {formatDateTime(document.created_at) ?? '—'}</p>
      <p><strong>vacancy_id:</strong> {document.vacancy_id ?? '—'}</p>

      <div>
        <h4 className="vacancy-details__section-title">generation_metadata</h4>
        {metadataEntries.length ? (
          <ul className="vacancy-details__metadata-list">
            {metadataEntries.map(([key, value]) => (
              <li key={key}>
                <strong>{key}:</strong> {key.includes('at') ? (formatDateTime(value) ?? String(value)) : String(value)}
              </li>
            ))}
          </ul>
        ) : (
          <p className="vacancy-details__hint-text">Metadata is not available for this draft.</p>
        )}
      </div>

      <button
        className="recommendations-toolbar__button recommendations-toolbar__button--secondary"
        type="button"
        onClick={() => onRegenerate(type)}
      >
        Regenerate {type === 'resume' ? 'resume' : 'cover letter'}
      </button>
    </article>
  );
}

export default function VacancyDetailsPage() {
  const { vacancyId } = useParams();
  const isMountedRef = useRef(true);

  const [vacancy, setVacancy] = useState(null);
  const [tailoring, setTailoring] = useState(null);
  const [loading, setLoading] = useState(true);
  const [vacancyError, setVacancyError] = useState('');
  const [tailoringError, setTailoringError] = useState('');
  const [isRefreshingTailoring, setIsRefreshingTailoring] = useState(false);
  const [isGeneratingResume, setIsGeneratingResume] = useState(false);
  const [isGeneratingCoverLetter, setIsGeneratingCoverLetter] = useState(false);
  const [generateError, setGenerateError] = useState('');
  const [approveError, setApproveError] = useState('');
  const [documentsError, setDocumentsError] = useState('');
  const [documentsLoading, setDocumentsLoading] = useState(false);
  const [isRefreshingDocuments, setIsRefreshingDocuments] = useState(false);
  const [resumeDocuments, setResumeDocuments] = useState([]);
  const [coverLetterDocuments, setCoverLetterDocuments] = useState([]);
  const [approvingResumeById, setApprovingResumeById] = useState({});
  const [approvingCoverLetterById, setApprovingCoverLetterById] = useState({});
  const [editingDocumentKey, setEditingDocumentKey] = useState('');
  const [editDraft, setEditDraft] = useState({ title: '', content_text: '' });
  const [savingEditByKey, setSavingEditByKey] = useState({});
  const [editError, setEditError] = useState('');
  const [editSuccess, setEditSuccess] = useState('');
  const [lastGeneratedResult, setLastGeneratedResult] = useState(null);

  const clearActionFeedback = useCallback(() => {
    setGenerateError('');
    setApproveError('');
    setEditError('');
    setEditSuccess('');
    setLastGeneratedResult(null);
  }, []);

  const startEditingDocument = useCallback((type, item) => {
    setEditError('');
    setEditSuccess('');
    setEditingDocumentKey(`${type}:${item.id}`);
    setEditDraft({
      title: item.title ?? '',
      content_text: item.content_text ?? '',
    });
  }, []);

  const cancelEditingDocument = useCallback(() => {
    setEditingDocumentKey('');
    setEditDraft({ title: '', content_text: '' });
  }, []);

  const applyUpdatedDocument = useCallback((type, updated) => {
    if (type === 'resume') {
      setResumeDocuments((current) => current.map((item) => (item.id === updated.id ? updated : item)));
    } else {
      setCoverLetterDocuments((current) => current.map((item) => (item.id === updated.id ? updated : item)));
    }

    setLastGeneratedResult((current) => {
      if (!current?.document || current.type !== type || current.document.id !== updated.id) {
        return current;
      }
      return { ...current, document: updated };
    });
  }, []);

  const saveEditingDocument = useCallback(async (type, id) => {
    const key = `${type}:${id}`;
    setEditError('');
    setEditSuccess('');
    setSavingEditByKey((current) => ({ ...current, [key]: true }));

    const payload = {
      title: editDraft.title.trim() || null,
      content_text: editDraft.content_text,
    };

    try {
      const updated = type === 'resume'
        ? await updateResumeVersion(DEFAULT_PROFILE_ID, id, payload)
        : await updateCoverLetterVersion(DEFAULT_PROFILE_ID, id, payload);

      applyUpdatedDocument(type, updated);
      setEditSuccess(`${getDocumentTypeLabel(type)} draft saved.`);
      setEditingDocumentKey('');
    } catch (requestError) {
      setEditError(getUserFacingError(requestError, `Failed to save ${getDocumentTypeLabel(type).toLowerCase()} draft.`));
    } finally {
      setSavingEditByKey((current) => ({ ...current, [key]: false }));
    }
  }, [applyUpdatedDocument, editDraft.content_text, editDraft.title]);

  const loadTailoring = useCallback(async () => {
    setTailoringError('');

    try {
      const tailoringResponse = await getTailoring(DEFAULT_PROFILE_ID, vacancyId);
      setTailoring(tailoringResponse);
    } catch (requestError) {
      setTailoring(null);
      setTailoringError(getUserFacingError(requestError, 'Не удалось загрузить мэтчинг.'));
    }
  }, [vacancyId]);

  const refreshTailoring = useCallback(async () => {
    setIsRefreshingTailoring(true);
    await loadTailoring();
    setIsRefreshingTailoring(false);
  }, [loadTailoring]);

  const loadDocuments = useCallback(async (options = {}) => {
    const { silent = false } = options;

    if (silent) {
      setIsRefreshingDocuments(true);
    } else {
      setDocumentsLoading(true);
    }
    setDocumentsError('');

    try {
      const [resumeResponse, coverLetterResponse] = await Promise.all([
        listResumeVersions(DEFAULT_PROFILE_ID),
        listCoverLetterVersions(DEFAULT_PROFILE_ID),
      ]);
      if (!isMountedRef.current) {
        return;
      }
      const numericVacancyId = Number(vacancyId);

      const filteredResumes = resumeResponse.filter((item) => item.vacancy_id === numericVacancyId);
      const filteredLetters = coverLetterResponse.filter((item) => item.vacancy_id === numericVacancyId);
      const sortByCreatedAtDesc = (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime();

      setResumeDocuments(filteredResumes.sort(sortByCreatedAtDesc));
      setCoverLetterDocuments(filteredLetters.sort(sortByCreatedAtDesc));
    } catch (requestError) {
      if (!isMountedRef.current) {
        return;
      }
      setDocumentsError(getUserFacingError(requestError, 'Не удалось загрузить документы для этой вакансии.'));
    } finally {
      if (isMountedRef.current) {
        if (silent) {
          setIsRefreshingDocuments(false);
        } else {
          setDocumentsLoading(false);
        }
      }
    }
  }, [vacancyId]);

  const refreshDocuments = useCallback(async () => {
    await loadDocuments({ silent: true });
  }, [loadDocuments]);

  const handleResumeGeneration = useCallback(async () => {
    setIsGeneratingResume(true);
    setGenerateError('');
    setApproveError('');
    setLastGeneratedResult(null);

    try {
      const createdDraft = await generateResumeDraft(DEFAULT_PROFILE_ID, vacancyId);
      setLastGeneratedResult({ type: 'resume', document: createdDraft });
      await loadDocuments({ silent: true });
    } catch (requestError) {
      setGenerateError(getUserFacingError(requestError, 'Failed to generate resume draft.'));
    } finally {
      setIsGeneratingResume(false);
    }
  }, [loadDocuments, vacancyId]);

  const handleCoverLetterGeneration = useCallback(async () => {
    setIsGeneratingCoverLetter(true);
    setGenerateError('');
    setApproveError('');
    setLastGeneratedResult(null);

    try {
      const createdDraft = await generateCoverLetterDraft(DEFAULT_PROFILE_ID, vacancyId);
      setLastGeneratedResult({ type: 'cover_letter', document: createdDraft });
      await loadDocuments({ silent: true });
    } catch (requestError) {
      setGenerateError(getUserFacingError(requestError, 'Failed to generate cover letter draft.'));
    } finally {
      setIsGeneratingCoverLetter(false);
    }
  }, [loadDocuments, vacancyId]);

  const handleRegenerate = useCallback((type) => {
    if (type === 'resume') {
      void handleResumeGeneration();
      return;
    }

    void handleCoverLetterGeneration();
  }, [handleCoverLetterGeneration, handleResumeGeneration]);

  const handleApproveResume = useCallback(async (id) => {
    setApproveError('');
    setGenerateError('');
    setLastGeneratedResult(null);
    setApprovingResumeById((current) => ({ ...current, [id]: true }));

    try {
      const approved = await approveResumeVersion(DEFAULT_PROFILE_ID, id);
      setResumeDocuments((current) => current.map((item) => (item.id === id ? approved : item)));
    } catch (requestError) {
      setApproveError(getUserFacingError(requestError, 'Failed to approve resume draft.'));
    } finally {
      setApprovingResumeById((current) => ({ ...current, [id]: false }));
    }
  }, []);

  const handleApproveCoverLetter = useCallback(async (id) => {
    setApproveError('');
    setGenerateError('');
    setLastGeneratedResult(null);
    setApprovingCoverLetterById((current) => ({ ...current, [id]: true }));

    try {
      const approved = await approveCoverLetterVersion(DEFAULT_PROFILE_ID, id);
      setCoverLetterDocuments((current) => current.map((item) => (item.id === id ? approved : item)));
    } catch (requestError) {
      setApproveError(getUserFacingError(requestError, 'Failed to approve cover letter draft.'));
    } finally {
      setApprovingCoverLetterById((current) => ({ ...current, [id]: false }));
    }
  }, []);

  useEffect(() => {
    isMountedRef.current = true;
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
            setVacancyError(getUserFacingError(innerError, 'Не удалось загрузить вакансию.'));
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
            setTailoringError(getUserFacingError(innerError, 'Не удалось загрузить мэтчинг.'));
          }
        }
      } finally {
        if (isActive) {
          setLoading(false);
        }
      }
    }

    clearActionFeedback();
    loadPageData();
    loadDocuments();

    return () => {
      isActive = false;
      isMountedRef.current = false;
    };
  }, [clearActionFeedback, loadDocuments, vacancyId]);

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
        <p className="flow-hint">Шаг flow: проверьте tailoring и затем переходите к генерации документов ниже.</p>

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

      <section className="vacancy-details__documents">
        <h2 className="vacancy-details__section-title">Document generation</h2>
        <p className="flow-hint">Следующий шаг: сгенерируйте draft и подтвердите (approve) нужную версию.</p>

        {generateError ? <ErrorBanner message={`Generate action: ${generateError}`} /> : null}
        {approveError ? <ErrorBanner message={`Approve action: ${approveError}`} /> : null}
        {editError ? <ErrorBanner message={`Edit action: ${editError}`} /> : null}
        {documentsError ? <ErrorBanner message={`Load documents: ${documentsError}`} /> : null}
        {editSuccess ? <p className="vacancy-details__docgen-success">{editSuccess}</p> : null}

        <div className="vacancy-details__docgen-actions">
          <button
            className="recommendations-toolbar__button"
            type="button"
            onClick={handleResumeGeneration}
            disabled={isGeneratingResume}
          >
            {isGeneratingResume ? 'Generating resume draft...' : (resumeDocuments.length ? 'Regenerate resume draft' : 'Generate resume draft')}
          </button>
          <button
            className="recommendations-toolbar__button recommendations-toolbar__button--secondary"
            type="button"
            onClick={refreshDocuments}
            disabled={documentsLoading || isRefreshingDocuments}
          >
            {isRefreshingDocuments ? 'Refreshing documents...' : 'Обновить документы'}
          </button>
          <button
            className="recommendations-toolbar__button recommendations-toolbar__button--secondary"
            type="button"
            onClick={handleCoverLetterGeneration}
            disabled={isGeneratingCoverLetter}
          >
            {isGeneratingCoverLetter ? 'Generating cover letter draft...' : (coverLetterDocuments.length ? 'Regenerate cover letter draft' : 'Generate cover letter draft')}
          </button>
        </div>

        {documentsLoading ? <Loading message="Loading vacancy documents..." /> : null}

        <GenerationResultBlock result={lastGeneratedResult} onRegenerate={handleRegenerate} />

        {!documentsLoading ? (
          <div className="vacancy-details__docgen-list">
            <article className="vacancy-details__docgen-result">
              <h3 className="vacancy-details__section-title">Resume versions (current vacancy)</h3>
              {resumeDocuments.length ? (
                <ul className="vacancy-details__doc-list">
                  {resumeDocuments.map((item) => (
                    <li key={item.id} className="vacancy-details__doc-item">
                      <p><strong>title:</strong> {getSafeText(item.title, '—')}</p>
                      <p><strong>status:</strong> {getSafeText(item.status, '—')}</p>
                      <p><strong>created_at:</strong> {formatDateTime(item.created_at) ?? '—'}</p>
                      <p><strong>approved_at:</strong> {formatDateTime(item.approved_at) ?? '—'}</p>
                      <p><strong>vacancy_id:</strong> {item.vacancy_id ?? '—'}</p>
                      <p className="vacancy-details__doc-meta"><strong>generation:</strong> {renderMetadataCompact(item.generation_metadata)}</p>
                      <h4 className="vacancy-details__section-title">content_text preview</h4>
                      <pre className="vacancy-details__description">{toPreviewText(item.content_text)}</pre>
                      {item.status === 'draft' ? (
                        <button
                          className="recommendations-toolbar__button recommendations-toolbar__button--secondary"
                          type="button"
                          onClick={() => startEditingDocument('resume', item)}
                        >
                          Edit
                        </button>
                      ) : null}
                      {editingDocumentKey === `resume:${item.id}` ? (
                        <div className="vacancy-details__edit-panel">
                          <label className="field-label" htmlFor={`resume-title-${item.id}`}>Title</label>
                          <input
                            id={`resume-title-${item.id}`}
                            className="input"
                            value={editDraft.title}
                            onChange={(event) => setEditDraft((current) => ({ ...current, title: event.target.value }))}
                          />
                          <label className="field-label" htmlFor={`resume-content-${item.id}`}>Content text</label>
                          <textarea
                            id={`resume-content-${item.id}`}
                            className="textarea"
                            rows={8}
                            value={editDraft.content_text}
                            onChange={(event) => setEditDraft((current) => ({ ...current, content_text: event.target.value }))}
                          />
                          {(editDraft.title !== (item.title ?? '') || editDraft.content_text !== (item.content_text ?? '')) ? (
                            <p className="vacancy-details__edit-warning">You have unsaved changes.</p>
                          ) : null}
                          <div className="vacancy-details__edit-actions">
                            <button
                              className="recommendations-toolbar__button"
                              type="button"
                              onClick={() => saveEditingDocument('resume', item.id)}
                              disabled={Boolean(savingEditByKey[`resume:${item.id}`])}
                            >
                              {savingEditByKey[`resume:${item.id}`] ? 'Saving...' : 'Save'}
                            </button>
                            <button
                              className="recommendations-toolbar__button recommendations-toolbar__button--secondary"
                              type="button"
                              onClick={cancelEditingDocument}
                              disabled={Boolean(savingEditByKey[`resume:${item.id}`])}
                            >
                              Cancel
                            </button>
                          </div>
                        </div>
                      ) : null}
                      {item.status === 'draft' ? (
                        <button
                          className="recommendations-toolbar__button"
                          type="button"
                          onClick={() => handleApproveResume(item.id)}
                          disabled={Boolean(approvingResumeById[item.id])}
                        >
                          {approvingResumeById[item.id] ? 'Approving resume...' : 'Approve resume'}
                        </button>
                      ) : (
                        <p className="vacancy-details__doc-approved">Approved / finalized</p>
                      )}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="vacancy-details__hint-text">Для этой вакансии пока нет resume versions.</p>
              )}
            </article>

            <article className="vacancy-details__docgen-result">
              <h3 className="vacancy-details__section-title">Cover letter versions (current vacancy)</h3>
              {coverLetterDocuments.length ? (
                <ul className="vacancy-details__doc-list">
                  {coverLetterDocuments.map((item) => (
                    <li key={item.id} className="vacancy-details__doc-item">
                      <p><strong>title:</strong> {getSafeText(item.title, '—')}</p>
                      <p><strong>status:</strong> {getSafeText(item.status, '—')}</p>
                      <p><strong>created_at:</strong> {formatDateTime(item.created_at) ?? '—'}</p>
                      <p><strong>approved_at:</strong> {formatDateTime(item.approved_at) ?? '—'}</p>
                      <p><strong>vacancy_id:</strong> {item.vacancy_id ?? '—'}</p>
                      <p className="vacancy-details__doc-meta"><strong>generation:</strong> {renderMetadataCompact(item.generation_metadata)}</p>
                      <h4 className="vacancy-details__section-title">content_text preview</h4>
                      <pre className="vacancy-details__description">{toPreviewText(item.content_text)}</pre>
                      {item.status === 'draft' ? (
                        <button
                          className="recommendations-toolbar__button recommendations-toolbar__button--secondary"
                          type="button"
                          onClick={() => startEditingDocument('cover_letter', item)}
                        >
                          Edit
                        </button>
                      ) : null}
                      {editingDocumentKey === `cover_letter:${item.id}` ? (
                        <div className="vacancy-details__edit-panel">
                          <label className="field-label" htmlFor={`letter-title-${item.id}`}>Title</label>
                          <input
                            id={`letter-title-${item.id}`}
                            className="input"
                            value={editDraft.title}
                            onChange={(event) => setEditDraft((current) => ({ ...current, title: event.target.value }))}
                          />
                          <label className="field-label" htmlFor={`letter-content-${item.id}`}>Content text</label>
                          <textarea
                            id={`letter-content-${item.id}`}
                            className="textarea"
                            rows={8}
                            value={editDraft.content_text}
                            onChange={(event) => setEditDraft((current) => ({ ...current, content_text: event.target.value }))}
                          />
                          {(editDraft.title !== (item.title ?? '') || editDraft.content_text !== (item.content_text ?? '')) ? (
                            <p className="vacancy-details__edit-warning">You have unsaved changes.</p>
                          ) : null}
                          <div className="vacancy-details__edit-actions">
                            <button
                              className="recommendations-toolbar__button"
                              type="button"
                              onClick={() => saveEditingDocument('cover_letter', item.id)}
                              disabled={Boolean(savingEditByKey[`cover_letter:${item.id}`])}
                            >
                              {savingEditByKey[`cover_letter:${item.id}`] ? 'Saving...' : 'Save'}
                            </button>
                            <button
                              className="recommendations-toolbar__button recommendations-toolbar__button--secondary"
                              type="button"
                              onClick={cancelEditingDocument}
                              disabled={Boolean(savingEditByKey[`cover_letter:${item.id}`])}
                            >
                              Cancel
                            </button>
                          </div>
                        </div>
                      ) : null}
                      {item.status === 'draft' ? (
                        <button
                          className="recommendations-toolbar__button"
                          type="button"
                          onClick={() => handleApproveCoverLetter(item.id)}
                          disabled={Boolean(approvingCoverLetterById[item.id])}
                        >
                          {approvingCoverLetterById[item.id] ? 'Approving cover letter...' : 'Approve cover letter'}
                        </button>
                      ) : (
                        <p className="vacancy-details__doc-approved">Approved / finalized</p>
                      )}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="vacancy-details__hint-text">Для этой вакансии пока нет cover letter versions.</p>
              )}
            </article>
          </div>
        ) : null}

        <p className="vacancy-details__hint-text">
          Need advanced edits?{' '}
          <Link className="vacancy-details__link" to="/settings">Open full editor in Settings</Link>
        </p>
      </section>
    </section>
  );
}
