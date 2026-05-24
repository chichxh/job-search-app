import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useParams } from 'react-router-dom';

import {
  approveCoverLetterVersion,
  approveResumeVersion,
  createApplication,
  createHhApplyRun,
  getHhBrowserConnectionStatus,
  generateCoverLetterDraft,
  generateResumeDraft,
  getTailoring,
  getVacancyById,
  listHhApplyRuns,
  listCoverLetterVersions,
  listHhManagedResumes,
  listResumeVersions,
  updateCoverLetterVersion,
  updateResumeVersion,
} from '../api/endpoints.js';
import { useAuth } from '../auth/useAuth.js';
import ErrorBanner from '../components/ErrorBanner.jsx';
import Loading from '../components/Loading.jsx';
import MetricTile from '../components/ui/MetricTile.jsx';
import PageHeader from '../components/ui/PageHeader.jsx';
import SectionCard from '../components/ui/SectionCard.jsx';
import StatusPill from '../components/ui/StatusPill.jsx';
import VerdictBadge from '../components/ui/VerdictBadge.jsx';
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
  return type === 'resume' ? 'Резюме' : 'Сопроводительное письмо';
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
    return 'Нет метаданных генерации';
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

const HH_BROWSER_SESSION_META = {
  connected: { label: 'HH сессия активна', tone: 'success' },
  requires_reauth: { label: 'Нужно переподключить HH', tone: 'danger' },
  failed: { label: 'Ошибка HH сессии', tone: 'danger' },
  disconnected: { label: 'HH не подключён', tone: 'muted' },
  connecting: { label: 'Идёт подключение HH', tone: 'accent' },
  awaiting_identifier: { label: 'Нужен логин HH', tone: 'info' },
  awaiting_password: { label: 'Нужен пароль HH', tone: 'info' },
  awaiting_code: { label: 'Нужен код подтверждения HH', tone: 'info' },
};

const HH_APPLY_STATUS_META = {
  queued: { label: 'В очереди', tone: 'accent' },
  opening_vacancy: { label: 'Открываем вакансию', tone: 'info' },
  awaiting_resume_selection: { label: 'Выбираем HH-резюме', tone: 'info' },
  awaiting_cover_letter: { label: 'Заполняем cover letter', tone: 'info' },
  submitting: { label: 'Отправляем отклик', tone: 'accent' },
  submitted: { label: 'Отправлено', tone: 'success' },
  failed: { label: 'Не отправлено', tone: 'danger' },
  retryable_failed: { label: 'Ошибка, можно повторить', tone: 'danger' },
};

const HH_APPLY_RESULT_TYPE_META = {
  submitted: { label: 'Отклик отправлен', tone: 'success' },
  dry_run_submitted: { label: 'Dry-run завершён', tone: 'info' },
  already_applied: { label: 'Вы уже откликались', tone: 'info' },
};

function getApplyPrivacyNote(managedResume) {
  if (!managedResume) {
    return '';
  }

  const autoHideEnabled = managedResume.auto_hide_from_all_enabled !== false;
  if (!autoHideEnabled) {
    return 'Автоскрытие отключено: перед откликом система не будет принудительно скрывать резюме от всех.';
  }

  if (managedResume.current_visibility_mode === 'unknown') {
    return 'Перед откликом запустится privacy pre-check: система проверит и при необходимости скроет резюме от всех.';
  }

  return 'Включён safe-режим: перед откликом система проверит, что резюме скрыто от всех, и при необходимости применит скрытие.';
}

function isHhSessionActive(status) {
  return Boolean(status?.status === 'connected' && status?.session_present && !status?.requires_reauth);
}

function formatApplyResultType(run) {
  if (!run?.result_type) {
    return '—';
  }
  return HH_APPLY_RESULT_TYPE_META[run.result_type]?.label ?? run.result_type;
}

function getApplyStatusMeta(status) {
  return HH_APPLY_STATUS_META[status] ?? { label: status || 'Неизвестно', tone: 'neutral' };
}

function GenerationResultBlock({ result, onRegenerate }) {
  if (!result?.document) {
    return null;
  }

  const { type, document } = result;

  return (
    <article className="vacancy-details__created-draft" aria-live="polite">
      <h3 className="vacancy-details__section-title">Новый черновик: {getDocumentTypeLabel(type)}</h3>
      <div className="inline-status-row">
        <StatusPill tone="success">status: {getSafeText(document.status, '—')}</StatusPill>
        <p className="vacancy-details__hint-text">Создан: {formatDateTime(document.created_at) ?? '—'}</p>
      </div>
      <p><strong>title:</strong> {getSafeText(document.title, '—')}</p>
      <p className="vacancy-details__doc-meta"><strong>генерация:</strong> {renderMetadataCompact(document.метаданные_генерации)}</p>
      <button
        className="button button--secondary"
        type="button"
        onClick={() => onRegenerate(type)}
      >
        Перегенерировать
      </button>
    </article>
  );
}

export default function VacancyDetailsPage() {
  const { profileId } = useAuth();
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
  const [trackSuccess, setTrackSuccess] = useState('');
  const [trackError, setTrackError] = useState('');
  const [isTrackingApplication, setIsTrackingApplication] = useState(false);
  const [hhBrowserStatus, setHhBrowserStatus] = useState(null);
  const [hhManagedResumes, setHhManagedResumes] = useState([]);
  const [hhApplyRuns, setHhApplyRuns] = useState([]);
  const [hhApplyLoading, setHhApplyLoading] = useState(false);
  const [hhApplyError, setHhApplyError] = useState('');
  const [hhApplySuccess, setHhApplySuccess] = useState('');
  const [hhApplyBusy, setHhApplyBusy] = useState(false);
  const [hhApplyOutcome, setHhApplyOutcome] = useState(null);
  const [selectedHhManagedResumeId, setSelectedHhManagedResumeId] = useState('');
  const [selectedCoverLetterId, setSelectedCoverLetterId] = useState('');

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
    setEditDraft({ title: item.title ?? '', content_text: item.content_text ?? '' });
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

    const payload = { title: editDraft.title.trim() || null, content_text: editDraft.content_text };

    try {
      const updated = type === 'resume'
        ? await updateResumeVersion(profileId, id, payload)
        : await updateCoverLetterVersion(profileId, id, payload);

      applyUpdatedDocument(type, updated);
      setEditSuccess(`${getDocumentTypeLabel(type)} сохранён.`);
      setEditingDocumentKey('');
    } catch (requestError) {
      setEditError(getUserFacingError(requestError, `Не удалось сохранить ${getDocumentTypeLabel(type).toLowerCase()} draft.`));
    } finally {
      setSavingEditByKey((current) => ({ ...current, [key]: false }));
    }
  }, [applyUpdatedDocument, editDraft.content_text, editDraft.title, profileId]);

  const loadTailoring = useCallback(async () => {
    setTailoringError('');

    try {
      const tailoringResponse = await getTailoring(profileId, vacancyId);
      setTailoring(tailoringResponse);
    } catch (requestError) {
      setTailoring(null);
      setTailoringError(getUserFacingError(requestError, 'Не удалось загрузить мэтчинг.'));
    }
  }, [profileId, vacancyId]);

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
        listResumeVersions(profileId),
        listCoverLetterVersions(profileId),
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
  }, [profileId, vacancyId]);

  const refreshDocuments = useCallback(async () => {
    await loadDocuments({ silent: true });
  }, [loadDocuments]);

  const loadHhApplyContext = useCallback(async () => {
    setHhApplyLoading(true);
    setHhApplyError('');
    try {
      const [browserStatusResponse, managedResumesResponse, applyRunsResponse] = await Promise.all([
        getHhBrowserConnectionStatus(),
        listHhManagedResumes(),
        listHhApplyRuns(),
      ]);

      if (!isMountedRef.current) {
        return;
      }

      setHhBrowserStatus(browserStatusResponse);
      setHhManagedResumes(managedResumesResponse);
      setHhApplyRuns(applyRunsResponse);
    } catch (requestError) {
      if (!isMountedRef.current) {
        return;
      }
      setHhApplyError(getUserFacingError(requestError, 'Не удалось загрузить HH apply контекст.'));
    } finally {
      if (isMountedRef.current) {
        setHhApplyLoading(false);
      }
    }
  }, []);

  const handleRunHhApply = useCallback(async () => {
    if (!vacancyId || !selectedHhManagedResumeId) {
      return;
    }

    setHhApplyError('');
    setHhApplySuccess('');
    setHhApplyOutcome(null);
    setHhApplyBusy(true);
    try {
      const response = await createHhApplyRun({
        vacancy_id: Number(vacancyId),
        hh_resume_managed_id: Number(selectedHhManagedResumeId),
        cover_letter_version_id: selectedCoverLetterId ? Number(selectedCoverLetterId) : null,
      });
      const run = response?.hh_apply_run ?? response;
      setHhApplyRuns((current) => [run, ...current.filter((item) => item.id !== run.id)]);
      setHhApplyOutcome({
        run,
        selectedManagedResume: selectedManagedResume ?? null,
        selectedCoverLetter: selectedCoverLetter ?? null,
      });

      const safeResultMessage = getSafeText(run?.result_message, 'Отклик обработан.');
      const applyVisibilityReminder = 'HH может автоматически показать резюме работодателю, которому отправлен отклик.';
      if (run?.result_type === 'already_applied') {
        setHhApplySuccess(`На HH уже есть отклик. ${safeResultMessage} ${applyVisibilityReminder}`);
      } else if (run?.status === 'submitted') {
        setHhApplySuccess(`Отклик отправлен через HH. ${safeResultMessage} ${applyVisibilityReminder}`);
      } else if (run?.status === 'retryable_failed') {
        setHhApplySuccess(`Отклик не завершён: ошибку можно исправить и повторить. ${safeResultMessage}`);
      } else {
        setHhApplySuccess(`Запуск завершён со статусом ${run?.status}. ${safeResultMessage}`);
      }
    } catch (requestError) {
      setHhApplyError(getUserFacingError(requestError, 'Не удалось отправить отклик через HH.'));
    } finally {
      setHhApplyBusy(false);
    }
  }, [selectedCoverLetter, selectedCoverLetterId, selectedHhManagedResumeId, selectedManagedResume, vacancyId]);

  const handleTrackApplication = useCallback(async () => {
    if (!vacancyId) {
      return;
    }
    setTrackSuccess('');
    setTrackError('');
    setIsTrackingApplication(true);
    try {
      await createApplication(profileId, { vacancy_id: Number(vacancyId) });
      setTrackSuccess('Вакансия добавлена в воронку откликов.');
    } catch (requestError) {
      setTrackError(getUserFacingError(requestError, 'Не удалось добавить эту вакансию в отклики.'));
    } finally {
      setIsTrackingApplication(false);
    }
  }, [profileId, vacancyId]);

  const handleResumeGeneration = useCallback(async () => {
    setIsGeneratingResume(true);
    setGenerateError('');
    setApproveError('');
    setLastGeneratedResult(null);

    try {
      const createdDraft = await generateResumeDraft(profileId, vacancyId);
      setLastGeneratedResult({ type: 'resume', document: createdDraft });
      await loadDocuments({ silent: true });
    } catch (requestError) {
      setGenerateError(getUserFacingError(requestError, 'Не удалось сгенерировать резюме.'));
    } finally {
      setIsGeneratingResume(false);
    }
  }, [loadDocuments, profileId, vacancyId]);

  const handleCoverLetterGeneration = useCallback(async () => {
    setIsGeneratingCoverLetter(true);
    setGenerateError('');
    setApproveError('');
    setLastGeneratedResult(null);

    try {
      const createdDraft = await generateCoverLetterDraft(profileId, vacancyId);
      setLastGeneratedResult({ type: 'cover_letter', document: createdDraft });
      await loadDocuments({ silent: true });
    } catch (requestError) {
      setGenerateError(getUserFacingError(requestError, 'Не удалось сгенерировать сопроводительное письмо.'));
    } finally {
      setIsGeneratingCoverLetter(false);
    }
  }, [loadDocuments, profileId, vacancyId]);

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
      const approved = await approveResumeVersion(profileId, id);
      setResumeDocuments((current) => current.map((item) => (item.id === id ? approved : item)));
    } catch (requestError) {
      setApproveError(getUserFacingError(requestError, 'Не удалось одобрить резюме.'));
    } finally {
      setApprovingResumeById((current) => ({ ...current, [id]: false }));
    }
  }, [profileId]);

  const handleApproveCoverLetter = useCallback(async (id) => {
    setApproveError('');
    setGenerateError('');
    setLastGeneratedResult(null);
    setApprovingCoverLetterById((current) => ({ ...current, [id]: true }));

    try {
      const approved = await approveCoverLetterVersion(profileId, id);
      setCoverLetterDocuments((current) => current.map((item) => (item.id === id ? approved : item)));
    } catch (requestError) {
      setApproveError(getUserFacingError(requestError, 'Не удалось одобрить сопроводительное письмо.'));
    } finally {
      setApprovingCoverLetterById((current) => ({ ...current, [id]: false }));
    }
  }, [profileId]);

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
          getTailoring(profileId, vacancyId),
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
          const tailoringResponse = await getTailoring(profileId, vacancyId);
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
    loadHhApplyContext();

    return () => {
      isActive = false;
      isMountedRef.current = false;
    };
  }, [clearActionFeedback, loadDocuments, loadHhApplyContext, profileId, vacancyId]);

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

  const numericVacancyId = Number(vacancyId);
  const hhSessionActive = isHhSessionActive(hhBrowserStatus);
  const hhSessionMeta = HH_BROWSER_SESSION_META[hhBrowserStatus?.status] ?? { label: hhBrowserStatus?.status ?? 'Неизвестно', tone: 'neutral' };

  const managedResumesForVacancy = useMemo(
    () => hhManagedResumes.filter((item) => item.vacancy_id === numericVacancyId),
    [hhManagedResumes, numericVacancyId],
  );
  const managedResumesEligible = useMemo(
    () => hhManagedResumes.filter((item) => ['created', 'stale'].includes(item.status)),
    [hhManagedResumes],
  );
  const selectedManagedResume = managedResumesEligible.find((item) => String(item.id) === selectedHhManagedResumeId) ?? null;
  const selectedCoverLetter = coverLetterDocuments.find((item) => String(item.id) === selectedCoverLetterId) ?? null;
  const latestApplyRunForVacancy = hhApplyRuns.find((item) => item.vacancy_id === numericVacancyId) ?? null;
  const hasManagedResumeForVacancy = managedResumesForVacancy.length > 0;
  const hasAnyEligibleManagedResume = managedResumesEligible.length > 0;
  const shouldWarnUnknownVisibility = selectedManagedResume?.current_visibility_mode === 'unknown';
  const applyPrivacyNote = getApplyPrivacyNote(selectedManagedResume);
  const applyDisabled = !hhSessionActive || !selectedHhManagedResumeId || hhApplyBusy;
  const latestRunManagedResume = latestApplyRunForVacancy
    ? hhManagedResumes.find((item) => item.id === latestApplyRunForVacancy.hh_resume_managed_id) ?? null
    : null;
  const latestRunCoverLetter = latestApplyRunForVacancy
    ? coverLetterDocuments.find((item) => item.id === latestApplyRunForVacancy.source_cover_letter_version_id) ?? null
    : null;

  useEffect(() => {
    if (selectedHhManagedResumeId && managedResumesEligible.some((item) => String(item.id) === selectedHhManagedResumeId)) {
      return;
    }

    const preferred = managedResumesForVacancy[0] ?? managedResumesEligible[0] ?? null;
    setSelectedHhManagedResumeId(preferred ? String(preferred.id) : '');
  }, [managedResumesEligible, managedResumesForVacancy, selectedHhManagedResumeId]);

  useEffect(() => {
    if (!coverLetterDocuments.length) {
      if (selectedCoverLetterId) {
        setSelectedCoverLetterId('');
      }
      return;
    }

    if (selectedCoverLetterId && coverLetterDocuments.some((item) => String(item.id) === selectedCoverLetterId)) {
      return;
    }

    const preferred = coverLetterDocuments.find((item) => item.status === 'approved') ?? coverLetterDocuments[0];
    setSelectedCoverLetterId(preferred ? String(preferred.id) : '');
  }, [coverLetterDocuments, selectedCoverLetterId]);

  return (
    <section className="page-stack">
      <PageHeader
        eyebrow="Detail Workspace"
        title="Vacancy details"
        subtitle="Премиальный рабочий экран: summary вакансии, мэтчинг-объяснение и pipeline генерации документов."
      />

      {loading ? <Loading message="Загружаем детали вакансии..." /> : null}
      {!loading && vacancyError ? <ErrorBanner message={vacancyError} /> : null}

      {!loading && vacancy ? (
        <SectionCard className="vacancy-summary-card" title={vacancy.title} subtitle={getSafeText(vacancy.company_name ?? vacancy.company, 'Не указана компания')}>
          <div className="vacancy-summary-top">
            <MetricTile label="Локация" value={getSafeText(vacancy.location, 'Не указана')} />
            <MetricTile label="Зарплата" value={formatSalary(vacancy, { emptyLabel: 'Не указана', fromLabel: 'от', toLabel: 'до' })} tone="info" />
            <MetricTile label="Статус" value={vacancy.status ?? 'Не указан'} hint={`Источник: ${vacancy.source ?? '—'}`} />
            <MetricTile label="Обновлено" value={formatDateTime(vacancy.updated_at) ?? '—'} hint={`Создано: ${formatDateTime(vacancy.created_at) ?? '—'}`} />
          </div>
          <div className="vacancy-details__docgen-actions">
            <button className="button" type="button" onClick={handleTrackApplication} disabled={isTrackingApplication}>
              {isTrackingApplication ? 'Добавляем...' : 'Добавить в отклики'}
            </button>
            <Link className="vacancy-details__link" to="/applications">Открыть воронку откликов</Link>
            {vacancy.url ? <a className="vacancy-details__link" href={vacancy.url} target="_blank" rel="noreferrer">Открыть источник вакансии</a> : null}
          </div>
          {trackSuccess ? <p className="success-banner">{trackSuccess}</p> : null}
          {trackError ? <ErrorBanner message={trackError} /> : null}
          <h3 className="vacancy-details__section-title">Описание вакансии</h3>
          <pre className="vacancy-details__description">{vacancy.description ?? 'Описание отсутствует.'}</pre>
        </SectionCard>
      ) : null}

      <div className="details-layout">
        <SectionCard
          className="vacancy-details__matching"
          title="Matching & explanation"
          subtitle="Читаемое объяснение: итоговый скор, вердикт, пробелы и evidence."
          actions={(
            <button className="button" type="button" onClick={refreshTailoring} disabled={loading || isRefreshingTailoring}>
              Обновить мэтчинг
            </button>
          )}
        >
          {isRefreshingTailoring ? <Loading message="Обновляем мэтчинг..." /> : null}
          {!loading && (tailoringError || !tailoring) ? (
            <div className="vacancy-details__hint">
              {tailoringError ? <ErrorBanner message={tailoringError} /> : null}
              <p>Пересчитайте рекомендации и вернитесь на эту страницу.</p>
              <Link className="vacancy-details__link" to="/recommendations">Перейти на /recommendations</Link>
            </div>
          ) : null}

          {!loading && tailoring && hasTailoringSections ? (
            <>
              <div className="matching-highlight">
                <MetricTile label="Final score" value={formatConfidence(finalScore)} tone="info" />
                <MetricTile label="Verdict" value={<VerdictBadge verdict={verdict} />} />
              </div>

              {keywordsToAdd.length ? (
                <div>
                  <h3 className="vacancy-details__section-title">Keywords to add</h3>
                  <div className="chip-list">{keywordsToAdd.map((keyword) => <span className="chip" key={keyword}>{keyword}</span>)}</div>
                </div>
              ) : null}

              {missingMustHave.length ? (
                <div>
                  <h3 className="vacancy-details__section-title">Missing must-have</h3>
                  <ul className="structured-list">{missingMustHave.map((item) => <li key={item}>{item}</li>)}</ul>
                </div>
              ) : null}

              {missingNiceToHave.length ? (
                <div>
                  <h3 className="vacancy-details__section-title">Missing nice-to-have</h3>
                  <ul className="structured-list">{missingNiceToHave.map((item) => <li key={item}>{item}</li>)}</ul>
                </div>
              ) : null}

              {coverLetterPoints.length ? (
                <div>
                  <h3 className="vacancy-details__section-title">Cover letter focus points</h3>
                  <ul className="structured-list">{coverLetterPoints.map((item) => <li key={item}>{item}</li>)}</ul>
                </div>
              ) : null}

              {evidenceItems.length ? (
                <div>
                  <h3 className="vacancy-details__section-title">Evidence</h3>
                  <ul className="structured-list">
                    {evidenceItems.map((item, index) => {
                      const text = item.text ?? item.evidence_text ?? String(item);
                      const confidence = item.confidence;
                      return <li key={`${text}-${index}`}>{text} {confidence != null ? <StatusPill tone="info">confidence {formatConfidence(confidence)}</StatusPill> : null}</li>;
                    })}
                  </ul>
                </div>
              ) : null}
            </>
          ) : null}

          {!loading && tailoring && !hasTailoringSections ? (
            <details>
              <summary>Raw tailoring JSON</summary>
              <pre className="vacancy-details__description">{JSON.stringify(tailoring, null, 2)}</pre>
            </details>
          ) : null}
        </SectionCard>

        <SectionCard className="vacancy-details__documents" title="Document generation" subtitle="Сгенерируйте и согласуйте резюме/cover letter без выхода с экрана.">
          <div className="vacancy-details__docgen-actions">
            <button className="button" type="button" onClick={handleResumeGeneration} disabled={isGeneratingResume}>
              {isGeneratingResume ? 'Генерируем резюме...' : (resumeDocuments.length ? 'Перегенерировать resume draft' : 'Сгенерировать resume draft')}
            </button>
            <button className="button button--secondary" type="button" onClick={handleCoverLetterGeneration} disabled={isGeneratingCoverLetter}>
              {isGeneratingCoverLetter ? 'Генерируем cover letter...' : (coverLetterDocuments.length ? 'Перегенерировать cover letter draft' : 'Сгенерировать cover letter draft')}
            </button>
            <button className="button button--secondary" type="button" onClick={refreshDocuments} disabled={documentsLoading || isRefreshingDocuments}>
              {isRefreshingDocuments ? 'Обновляем...' : 'Обновить документы'}
            </button>
          </div>

          {generateError ? <ErrorBanner message={`Generate action: ${generateError}`} /> : null}
          {approveError ? <ErrorBanner message={`Approve action: ${approveError}`} /> : null}
          {editError ? <ErrorBanner message={`Edit action: ${editError}`} /> : null}
          {documentsError ? <ErrorBanner message={`Load documents: ${documentsError}`} /> : null}
          {editSuccess ? <p className="success-banner">{editSuccess}</p> : null}
          {documentsLoading ? <Loading message="Загружаем документы по вакансии..." /> : null}

          <GenerationResultBlock result={lastGeneratedResult} onRegenerate={handleRegenerate} />

          {!documentsLoading ? (
            <div className="vacancy-details__docgen-list">
              {[['resume', resumeDocuments], ['cover_letter', coverLetterDocuments]].map(([type, items]) => (
                <article className="vacancy-details__docgen-result" key={type}>
                  <h3 className="vacancy-details__section-title">{type === 'resume' ? 'Версии резюме' : 'Версии сопроводительных писем'}</h3>
                  {items.length ? (
                    <ul className="vacancy-details__doc-list">
                      {items.map((item) => (
                        <li key={item.id} className="vacancy-details__doc-item">
                          <div className="inline-status-row">
                            <p><strong>{getSafeText(item.title, '—')}</strong></p>
                            <StatusPill tone={item.status === 'approved' ? 'success' : 'neutral'}>{getSafeText(item.status, '—')}</StatusPill>
                          </div>
                          <p className="vacancy-details__hint-text">created {formatDateTime(item.created_at) ?? '—'} · approved {formatDateTime(item.approved_at) ?? '—'}</p>
                          <p className="vacancy-details__doc-meta"><strong>генерация:</strong> {renderMetadataCompact(item.метаданные_генерации)}</p>
                          <pre className="vacancy-details__description">{toPreviewText(item.content_text)}</pre>
                          {item.status === 'draft' ? (
                            <button className="button button--secondary" type="button" onClick={() => startEditingDocument(type, item)}>Изменить</button>
                          ) : null}
                          {editingDocumentKey === `${type}:${item.id}` ? (
                            <div className="vacancy-details__edit-panel">
                              <label className="field-label" htmlFor={`${type}-title-${item.id}`}>Название</label>
                              <input id={`${type}-title-${item.id}`} className="input" value={editDraft.title} onChange={(event) => setEditDraft((current) => ({ ...current, title: event.target.value }))} />
                              <label className="field-label" htmlFor={`${type}-content-${item.id}`}>Текст</label>
                              <textarea id={`${type}-content-${item.id}`} className="textarea" rows={8} value={editDraft.content_text} onChange={(event) => setEditDraft((current) => ({ ...current, content_text: event.target.value }))} />
                              <div className="vacancy-details__edit-actions">
                                <button className="button" type="button" onClick={() => saveEditingDocument(type, item.id)} disabled={Boolean(savingEditByKey[`${type}:${item.id}`])}>
                                  {savingEditByKey[`${type}:${item.id}`] ? 'Сохраняем...' : 'Сохранить'}
                                </button>
                                <button className="button button--secondary" type="button" onClick={cancelEditingDocument} disabled={Boolean(savingEditByKey[`${type}:${item.id}`])}>Отмена</button>
                              </div>
                            </div>
                          ) : null}
                          {item.status === 'draft' ? (
                            <button
                              className="button"
                              type="button"
                              onClick={() => (type === 'resume' ? handleApproveResume(item.id) : handleApproveCoverLetter(item.id))}
                              disabled={Boolean(type === 'resume' ? approvingResumeById[item.id] : approvingCoverLetterById[item.id])}
                            >
                              {type === 'resume'
                                ? (approvingResumeById[item.id] ? 'Подтверждаем резюме...' : 'Подтвердить резюме')
                                : (approvingCoverLetterById[item.id] ? 'Подтверждаем сопроводительное письмо...' : 'Подтвердить сопроводительное письмо')}
                            </button>
                          ) : (
                            <p className="vacancy-details__doc-approved">Подтверждено</p>
                          )}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="vacancy-details__hint-text">Пока нет документов для этой вакансии.</p>
                  )}
                </article>
              ))}
            </div>
          ) : null}

          <p className="vacancy-details__hint-text">Need advanced edits? <Link className="vacancy-details__link" to="/settings">Открыть полный редактор в настройках</Link></p>
        </SectionCard>

        <SectionCard
          className="vacancy-details__documents"
          title="Откликнуться через HH"
          subtitle="Компактный apply flow: выберите HH-резюме и cover letter, проверьте prerequisites и запустите отклик."
          actions={(
            <button className="button button--secondary" type="button" onClick={loadHhApplyContext} disabled={hhApplyLoading || hhApplyBusy}>
              {hhApplyLoading ? 'Обновляем HH данные...' : 'Обновить HH данные'}
            </button>
          )}
        >
          {hhApplyLoading ? <Loading message="Загружаем HH apply контекст..." /> : null}
          {hhApplyError ? <ErrorBanner message={hhApplyError} /> : null}
          {hhApplySuccess ? <p className="success-banner">{hhApplySuccess}</p> : null}

          <div className="vacancy-details__hh-apply-grid">
            <article className="vacancy-details__docgen-result">
              <h3 className="vacancy-details__section-title">Prerequisites</h3>
              <div className="inline-status-row">
                <StatusPill tone={hhSessionMeta.tone}>HH сессия: {hhSessionMeta.label}</StatusPill>
                <p className="vacancy-details__hint-text">Проверено: {formatDateTime(hhBrowserStatus?.last_checked_at) ?? '—'}</p>
              </div>
              {!hhSessionActive ? (
                <p className="error-banner">
                  Для запуска отклика нужна активная HH browser session.
                  {' '}
                  <Link className="vacancy-details__link" to="/settings">Переподключить HH</Link>
                </p>
              ) : null}
              {!hasManagedResumeForVacancy ? (
                <p className="info-banner">
                  Для этой вакансии не найдено targeted HH-резюме.
                  {' '}
                  <Link className="vacancy-details__link" to="/settings">Создать targeted HH resume</Link>
                </p>
              ) : null}
              {!hasAnyEligibleManagedResume ? (
                <p className="error-banner">
                  Нет доступных managed HH-резюме для отклика (status created/stale). Сначала создайте HH-резюме.
                </p>
              ) : null}
              {shouldWarnUnknownVisibility ? (
                <p className="info-banner">
                  Visibility выбранного HH-резюме неизвестна. Если safe-режим включён, перед откликом запустится privacy pre-check.
                </p>
              ) : null}
              {selectedManagedResume ? (
                <p className={selectedManagedResume.auto_hide_from_all_enabled === false ? 'error-banner' : 'info-banner'}>
                  {applyPrivacyNote}
                </p>
              ) : null}
            </article>

            <article className="vacancy-details__docgen-result">
              <h3 className="vacancy-details__section-title">Параметры отклика</h3>
              <label className="field-label" htmlFor="hh-managed-resume-select">HH managed resume</label>
              <select
                id="hh-managed-resume-select"
                className="input"
                value={selectedHhManagedResumeId}
                onChange={(event) => setSelectedHhManagedResumeId(event.target.value)}
              >
                {!managedResumesEligible.length ? <option value="">Нет доступных HH-резюме</option> : null}
                {managedResumesEligible.map((item) => (
                  <option key={item.id} value={item.id}>
                    {(item.title || `HH resume #${item.id}`)} · vacancy_id={item.vacancy_id ?? '—'} · {item.status}
                  </option>
                ))}
              </select>

              <label className="field-label" htmlFor="cover-letter-select">Cover letter version (опционально)</label>
              <select
                id="cover-letter-select"
                className="input"
                value={selectedCoverLetterId}
                onChange={(event) => setSelectedCoverLetterId(event.target.value)}
              >
                <option value="">Без cover letter</option>
                {coverLetterDocuments.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.title || `Cover letter #${item.id}`} · {item.status}
                  </option>
                ))}
              </select>

              {selectedCoverLetter ? (
                <div>
                  <p className="vacancy-details__hint-text">
                    Preview selected cover letter: {selectedCoverLetter.title || `#${selectedCoverLetter.id}`}
                    {' · '}
                    {selectedCoverLetter.status}
                  </p>
                  <pre className="vacancy-details__description">{toPreviewText(selectedCoverLetter.content_text, 360)}</pre>
                </div>
              ) : (
                <p className="vacancy-details__hint-text">Можно отправить отклик без cover letter.</p>
              )}

              <button className="button" type="button" onClick={handleRunHhApply} disabled={applyDisabled}>
                {hhApplyBusy ? 'Отправляем отклик через HH...' : 'Откликнуться через HH'}
              </button>
              {applyDisabled ? (
                <p className="vacancy-details__hint-text">
                  {!hhSessionActive
                    ? 'Кнопка недоступна: сначала подключите активную HH сессию.'
                    : (!selectedHhManagedResumeId ? 'Кнопка недоступна: выберите HH managed resume.' : 'Идёт запуск apply, подождите завершения.')}
                </p>
              ) : null}
            </article>
          </div>

          <article className="vacancy-details__docgen-result">
            <h3 className="vacancy-details__section-title">Последний HH apply run по вакансии</h3>
            {!latestApplyRunForVacancy ? (
              <p className="vacancy-details__hint-text">По этой вакансии ещё нет запусков HH apply.</p>
            ) : (
              <>
                <div className="inline-status-row">
                  <StatusPill tone={getApplyStatusMeta(latestApplyRunForVacancy.status).tone}>
                    status: {getApplyStatusMeta(latestApplyRunForVacancy.status).label}
                  </StatusPill>
                  <StatusPill tone={HH_APPLY_RESULT_TYPE_META[latestApplyRunForVacancy.result_type]?.tone ?? 'neutral'}>
                    result: {formatApplyResultType(latestApplyRunForVacancy)}
                  </StatusPill>
                </div>
                <ul className="structured-list">
                  <li>
                    <strong>HH resume used:</strong>
                    {' '}
                    {latestRunManagedResume
                      ? `${latestRunManagedResume.title || `HH resume #${latestRunManagedResume.id}`} (#${latestRunManagedResume.id})`
                      : `#${latestApplyRunForVacancy.hh_resume_managed_id}`}
                  </li>
                  <li>
                    <strong>Cover letter used:</strong>
                    {' '}
                    {latestRunCoverLetter
                      ? `${latestRunCoverLetter.title || `Cover letter #${latestRunCoverLetter.id}`} (#${latestRunCoverLetter.id})`
                      : (latestApplyRunForVacancy.source_cover_letter_version_id ? `#${latestApplyRunForVacancy.source_cover_letter_version_id}` : 'без cover letter')}
                  </li>
                  <li><strong>Updated:</strong> {formatDateTime(latestApplyRunForVacancy.updated_at) ?? '—'}</li>
                  <li><strong>Finished:</strong> {formatDateTime(latestApplyRunForVacancy.finished_at) ?? '—'}</li>
                  <li><strong>Safe message:</strong> {getSafeText(latestApplyRunForVacancy.result_message, '—')}</li>
                  {latestApplyRunForVacancy.hh_vacancy_url ? (
                    <li>
                      <strong>HH vacancy:</strong>
                      {' '}
                      <a className="vacancy-details__link" href={latestApplyRunForVacancy.hh_vacancy_url} target="_blank" rel="noreferrer">Открыть HH vacancy</a>
                    </li>
                  ) : null}
                </ul>
              </>
            )}
          </article>

          {hhApplyOutcome?.run ? (
            <article className="vacancy-details__docgen-result">
              <h3 className="vacancy-details__section-title">Результат последнего запуска</h3>
              <div className="inline-status-row">
                <StatusPill tone={getApplyStatusMeta(hhApplyOutcome.run.status).tone}>
                  status: {getApplyStatusMeta(hhApplyOutcome.run.status).label}
                </StatusPill>
                <StatusPill tone={HH_APPLY_RESULT_TYPE_META[hhApplyOutcome.run.result_type]?.tone ?? 'neutral'}>
                  result: {formatApplyResultType(hhApplyOutcome.run)}
                </StatusPill>
              </div>
              <ul className="structured-list">
                <li>
                  <strong>HH resume used:</strong>
                  {' '}
                  {hhApplyOutcome.selectedManagedResume
                    ? `${hhApplyOutcome.selectedManagedResume.title || `HH resume #${hhApplyOutcome.selectedManagedResume.id}`} (#${hhApplyOutcome.selectedManagedResume.id})`
                    : `#${hhApplyOutcome.run.hh_resume_managed_id}`}
                </li>
                <li>
                  <strong>Cover letter used:</strong>
                  {' '}
                  {hhApplyOutcome.selectedCoverLetter
                    ? `${hhApplyOutcome.selectedCoverLetter.title || `Cover letter #${hhApplyOutcome.selectedCoverLetter.id}`} (#${hhApplyOutcome.selectedCoverLetter.id})`
                    : 'без cover letter'}
                </li>
                <li><strong>Last apply timestamp:</strong> {formatDateTime(hhApplyOutcome.run.finished_at ?? hhApplyOutcome.run.updated_at) ?? '—'}</li>
                <li><strong>Result summary:</strong> {getSafeText(hhApplyOutcome.run.result_message, '—')}</li>
              </ul>
              <p className="info-banner">
                Этот шаг обновляет только HH apply run. Автоматическая синхронизация в локальную воронку откликов будет добавлена отдельным шагом roadmap.
              </p>
              {hhApplyOutcome.run.status === 'retryable_failed' ? (
                <p className="info-banner">
                  Ошибка временная: проверьте HH-сессию/документы и повторите отклик кнопкой «Откликнуться через HH».
                </p>
              ) : null}
              {hhApplyOutcome.run.status === 'failed' ? (
                <p className="error-banner">
                  Отклик завершился ошибкой без возможности безопасного ретрая.
                </p>
              ) : null}
              {hhApplyOutcome.run.result_type === 'already_applied' ? (
                <p className="info-banner">
                  HH уже содержит ваш отклик на эту вакансию; это не ошибка.
                </p>
              ) : null}
            </article>
          ) : null}
        </SectionCard>
      </div>
    </section>
  );
}
