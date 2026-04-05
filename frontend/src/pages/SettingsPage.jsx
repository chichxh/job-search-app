import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';

import {
  approveCoverLetterVersion,
  approveResumeVersion,
  createAchievement,
  createCertificate,
  createCoverLetterVersion,
  createEducation,
  createExperience,
  createLanguage,
  createLink,
  createProject,
  createResumeVersion,
  createSkill,
  extractResumeImportFile,
  deleteAchievement,
  deleteCertificate,
  deleteCoverLetterVersion,
  deleteEducation,
  deleteExperience,
  deleteLanguage,
  deleteLink,
  deleteProject,
  deleteResumeVersion,
  deleteSkill,
  disconnectHh,
  getProfile,
  getHhConnectionStatus,
  importProfileFromHh,
  importProfileFromHhJson,
  parseResumeImportText,
  listAchievements,
  listCertificates,
  listCoverLetterVersions,
  listEducation,
  listExperiences,
  listLanguages,
  listLinks,
  listProjects,
  listResumeVersions,
  listSkills,
  listHhResumes,
  recomputeAllProfileData,
  recomputeRecommendations,
  updateAchievement,
  updateCertificate,
  updateCoverLetterVersion,
  updateEducation,
  updateExperience,
  updateLanguage,
  updateLink,
  updateProfile,
  updateProject,
  updateResumeVersion,
  updateSkill,
  applyResumeImportDraft,
  cancelHhBrowserConnection,
  checkHhBrowserSession,
  checkHhManagedResumeVisibility,
  createHhTargetedResume,
  disconnectHhBrowserConnection,
  getVacancies,
  getHhManagedResumeVisibility,
  hideHhManagedResumeFromAll,
  restoreHhBrowserSession,
  listHhManagedResumes,
  startHhOAuthConnect,
  getHhBrowserConnectState,
  startHhBrowserConnection,
  submitHhBrowserCode,
  submitHhBrowserIdentifier,
  submitHhBrowserPassword,
} from '../api/endpoints.js';
import ErrorBanner from '../components/ErrorBanner.jsx';
import Loading from '../components/Loading.jsx';
import DateField from '../components/forms/DateField.jsx';
import InlineEditorCard from '../components/forms/InlineEditorCard.jsx';
import Section from '../components/forms/Section.jsx';
import SelectField from '../components/forms/SelectField.jsx';
import SwitchField from '../components/forms/SwitchField.jsx';
import TagInput from '../components/forms/TagInput.jsx';
import TextAreaField from '../components/forms/TextAreaField.jsx';
import TextField from '../components/forms/TextField.jsx';
import { DEFAULT_LIMIT } from '../config.js';
import { useAuth } from '../auth/useAuth.js';

const EMPLOYMENT_OPTIONS = [
  { value: 'full_time', label: 'Полная занятость' },
  { value: 'part_time', label: 'Частичная занятость' },
  { value: 'contract', label: 'Контракт' },
  { value: 'internship', label: 'Стажировка' },
  { value: 'project', label: 'Проектная работа' },
  { value: 'volunteer', label: 'Волонтёрство' },
];

const SCHEDULE_OPTIONS = [
  { value: 'full_day', label: 'Полный день' },
  { value: 'shift', label: 'Сменный график' },
  { value: 'flexible', label: 'Гибкий график' },
  { value: 'remote', label: 'Удалённо' },
  { value: 'hybrid', label: 'Гибрид' },
];
const SUPPORTED_RESUME_IMPORT_EXTENSIONS = ['txt', 'md', 'docx', 'pdf', 'rtf'];
const DOCUMENT_STATUS_META = {
  draft: { label: 'Draft', tone: 'draft' },
  approved: { label: 'Approved', tone: 'approved' },
  archived: { label: 'Archived', tone: 'archived' },
};
const HH_BROWSER_STATUS_META = {
  disconnected: { label: 'Не подключено', tone: 'muted' },
  connecting: { label: 'Подключаем сессию', tone: 'accent' },
  awaiting_identifier: { label: 'Нужен логин (email/телефон)', tone: 'info' },
  awaiting_password: { label: 'Нужен пароль HH', tone: 'info' },
  awaiting_code: { label: 'Нужен код подтверждения', tone: 'info' },
  connected: { label: 'Подключено', tone: 'success' },
  requires_reauth: { label: 'Требуется переподключение', tone: 'danger' },
  failed: { label: 'Ошибка подключения', tone: 'danger' },
};
const HH_BROWSER_SESSION_HEALTH_META = {
  connected: {
    title: 'Сессия HH активна',
    text: 'Можно продолжать работу: серверная сессия сохранена и выглядит рабочей.',
    tone: 'success',
  },
  requires_reauth: {
    title: 'Нужно переподключение HH',
    text: 'Текущая сессия больше не подходит. Запустите переподключение и пройдите вход заново.',
    tone: 'danger',
  },
  failed: {
    title: 'Подключение завершилось с ошибкой',
    text: 'Попробуйте проверить состояние сессии. Если ошибка повторится — переподключите HH.',
    tone: 'danger',
  },
  disconnected: {
    title: 'HH не подключён',
    text: 'Подключите HH, чтобы создать и сохранить серверную сессию.',
    tone: 'muted',
  },
  connecting: {
    title: 'Идёт подключение',
    text: 'Завершите текущий шаг входа, чтобы получить активную HH-сессию.',
    tone: 'accent',
  },
  awaiting_identifier: {
    title: 'Ожидается логин',
    text: 'Введите email или телефон HH для продолжения входа.',
    tone: 'info',
  },
  awaiting_password: {
    title: 'Ожидается пароль',
    text: 'Введите пароль HH, чтобы продолжить вход.',
    tone: 'info',
  },
  awaiting_code: {
    title: 'Ожидается код подтверждения',
    text: 'Введите код из SMS или приложения HH.',
    tone: 'info',
  },
};
const HH_MANAGED_RESUME_STATUS_META = {
  draft_local: { label: 'Локальный preview', tone: 'muted' },
  creating: { label: 'Создаётся', tone: 'accent' },
  created: { label: 'Создано', tone: 'success' },
  failed: { label: 'Ошибка', tone: 'danger' },
  stale: { label: 'Требует обновления', tone: 'info' },
};
const HH_VISIBILITY_MODE_META = {
  unknown: { label: 'Неизвестно', tone: 'muted' },
  public_default: { label: 'Видно работодателям (по умолчанию HH)', tone: 'danger' },
  hidden_from_all: { label: 'Скрыто от всех', tone: 'success' },
  visible_selected_employers: { label: 'Видно выбранным работодателям (после отклика HH)', tone: 'info' },
  change_pending: { label: 'Обновляем...', tone: 'accent' },
  change_failed: { label: 'Не удалось применить', tone: 'danger' },
};
const HH_VISIBILITY_STATUS_META = {
  idle: { label: 'Не проверяли', tone: 'muted' },
  checking: { label: 'Проверяем...', tone: 'accent' },
  updated: { label: 'Актуально', tone: 'success' },
  change_pending: { label: 'Меняем...', tone: 'accent' },
  check_failed: { label: 'Ошибка проверки', tone: 'danger' },
  change_failed: { label: 'Ошибка изменения', tone: 'danger' },
};

const emptyBySection = {
  skills: { name_raw: '', category: '', level: '', years: '', last_used_year: '', is_primary: false, evidence_text: '' },
  experiences: {
    company_name: '', position_title: '', location: '', start_date: '', end_date: '', is_current: false,
    responsibilities_text: '', achievements_text: '', tech_stack_text: '', employment_type: '',
  },
  projects: { name: '', role: '', description_text: '', start_date: '', end_date: '', tech_stack_text: '', url: '' },
  achievements: { title: '', metric: '', achieved_at: '', description_text: '', related_experience_id: '', related_project_id: '' },
  education: { institution: '', degree_level: '', field_of_study: '', start_year: '', end_year: '', description_text: '', gpa: '' },
  certificates: { name: '', issuer: '', issued_at: '', expires_at: '', url: '' },
  languages: { language: '', level: '' },
  links: { type: '', url: '', label: '' },
  resumes: { title: '', vacancy_id: '', content_text: '', status: 'draft', format: 'plain', source: 'user' },
  letters: { title: '', subject: '', vacancy_id: '', content_text: '', status: 'draft', source: 'user' },
};

export default function SettingsPage() {
  const { profileId } = useAuth();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [toast, setToast] = useState('');
  const [profileSaving, setProfileSaving] = useState(false);
  const [profile, setProfile] = useState({});
  const [teamPreferencesText, setTeamPreferencesText] = useState('{}');
  const [teamPreferencesError, setTeamPreferencesError] = useState('');
  const [savingByKey, setSavingByKey] = useState({});
  const [approvedOnlyResume, setApprovedOnlyResume] = useState(false);
  const [approvedOnlyLetter, setApprovedOnlyLetter] = useState(false);

  const [skills, setSkills] = useState([]);
  const [experiences, setExperiences] = useState([]);
  const [projects, setProjects] = useState([]);
  const [achievements, setAchievements] = useState([]);
  const [education, setEducation] = useState([]);
  const [certificates, setCertificates] = useState([]);
  const [languages, setLanguages] = useState([]);
  const [links, setLinks] = useState([]);
  const [resumes, setResumes] = useState([]);
  const [letters, setLetters] = useState([]);
  const [hhStatus, setHhStatus] = useState({ connected: false });
  const [hhBrowserStatus, setHhBrowserStatus] = useState(null);
  const [hhBrowserLoading, setHhBrowserLoading] = useState(false);
  const [hhBrowserBusy, setHhBrowserBusy] = useState(false);
  const [hhBrowserError, setHhBrowserError] = useState('');
  const [hhBrowserMessage, setHhBrowserMessage] = useState('');
  const [hhIdentifierType, setHhIdentifierType] = useState('phone');
  const [hhIdentifier, setHhIdentifier] = useState('');
  const [hhPassword, setHhPassword] = useState('');
  const [hhCode, setHhCode] = useState('');
  const [vacancies, setVacancies] = useState([]);
  const [hhManagedResumes, setHhManagedResumes] = useState([]);
  const [targetVacancyId, setTargetVacancyId] = useState('');
  const [targetResumeVersionId, setTargetResumeVersionId] = useState('');
  const [targetTitle, setTargetTitle] = useState('');
  const [targetSkillsFocusRaw, setTargetSkillsFocusRaw] = useState('');
  const [targetMaxExperiences, setTargetMaxExperiences] = useState('4');
  const [targetIncludeSkillLevels, setTargetIncludeSkillLevels] = useState(false);
  const [targetSummary, setTargetSummary] = useState('');
  const [targetDoNotHideFromAllEmployers, setTargetDoNotHideFromAllEmployers] = useState(false);
  const [hhTargetPreview, setHhTargetPreview] = useState(null);
  const [hhTargetLastResult, setHhTargetLastResult] = useState(null);
  const [hhTargetBusy, setHhTargetBusy] = useState(false);
  const [hhTargetError, setHhTargetError] = useState('');
  const [hhTargetMessage, setHhTargetMessage] = useState('');
  const [hhVisibilityBusyById, setHhVisibilityBusyById] = useState({});
  const [hhVisibilityError, setHhVisibilityError] = useState('');
  const [hhVisibilityMessage, setHhVisibilityMessage] = useState('');
  const [hhResumes, setHhResumes] = useState([]);
  const [hhResumeId, setHhResumeId] = useState('');
  const [hhBusy, setHhBusy] = useState(false);
  const [hhJsonRaw, setHhJsonRaw] = useState('');
  const [hhJsonConsent, setHhJsonConsent] = useState(false);
  const [hhJsonBusy, setHhJsonBusy] = useState(false);
  const [hhJsonError, setHhJsonError] = useState('');
  const [hhJsonResumeId, setHhJsonResumeId] = useState('');
  const [hhJsonImportSummary, setHhJsonImportSummary] = useState(null);
  const [resumeImportFile, setResumeImportFile] = useState(null);
  const [resumeImportBusy, setResumeImportBusy] = useState(false);
  const [resumeImportParseError, setResumeImportParseError] = useState('');
  const [resumeImportApplyError, setResumeImportApplyError] = useState('');
  const [resumeImportExtractionWarnings, setResumeImportExtractionWarnings] = useState([]);
  const [resumeImportExtractedTextLength, setResumeImportExtractedTextLength] = useState(0);
  const [resumeImportExtractedFileName, setResumeImportExtractedFileName] = useState('');
  const [resumeImportDraftResponse, setResumeImportDraftResponse] = useState(null);
  const [resumeImportApplySummary, setResumeImportApplySummary] = useState(null);
  useEffect(() => {
    async function loadData() {
      setLoading(true);
      setError('');
      try {
        const [
          profileData,
          experiencesData,
          projectsData,
          achievementsData,
          educationData,
          certificatesData,
          skillsData,
          languagesData,
          linksData,
          resumeData,
          letterData,
          vacanciesData,
          managedResumesData,
        ] = await Promise.all([
          getProfile(profileId),
          listExperiences(profileId),
          listProjects(profileId),
          listAchievements(profileId),
          listEducation(profileId),
          listCertificates(profileId),
          listSkills(profileId),
          listLanguages(profileId),
          listLinks(profileId),
          listResumeVersions(profileId),
          listCoverLetterVersions(profileId),
          getVacancies(),
          listHhManagedResumes(),
        ]);
        setProfile(profileData);
        setTeamPreferencesText(JSON.stringify(profileData.team_preferences_json ?? {}, null, 2));
        setExperiences(experiencesData.sort((a, b) => (a.start_date < b.start_date ? 1 : -1)));
        setProjects(projectsData);
        setAchievements(achievementsData);
        setEducation(educationData);
        setCertificates(certificatesData);
        setSkills(skillsData);
        setLanguages(languagesData);
        setLinks(linksData);
        setResumes(resumeData);
        setLetters(letterData);
        setVacancies(vacanciesData);
        setHhManagedResumes(managedResumesData);

        const [hhConnection, hhBrowserConnection] = await Promise.all([
          getHhConnectionStatus(),
          getHhBrowserConnectState(),
        ]);
        setHhStatus(hhConnection);
        setHhBrowserStatus(hhBrowserConnection);
        if (hhConnection.connected) {
          const resumes = await listHhResumes();
          setHhResumes(resumes);
          setHhResumeId(hhConnection.hh_resume_id ?? resumes[0]?.id ?? '');
        } else {
          setHhResumes([]);
          setHhResumeId('');
        }
      } catch (requestError) {
        setError(requestError.message || 'Ошибка загрузки настроек.');
      } finally {
        setLoading(false);
      }
    }

    loadData();
  }, [profileId]);

  useEffect(() => {
    const status = hhBrowserStatus?.status;
    if (!status || !['connecting', 'awaiting_identifier', 'awaiting_password', 'awaiting_code'].includes(status)) {
      return undefined;
    }

    const intervalId = window.setInterval(() => {
      refreshHhBrowserStatus();
    }, 3000);

    return () => window.clearInterval(intervalId);
  }, [hhBrowserStatus?.status]);

  const hhJsonParseResult = useMemo(() => {
    if (!hhJsonRaw.trim()) {
      return { error: '', payload: null };
    }
    try {
      return { error: '', payload: JSON.parse(hhJsonRaw) };
    } catch {
      return { error: 'Некорректный JSON: не удалось распарсить текст.', payload: null };
    }
  }, [hhJsonRaw]);

  const hhJsonPreview = useMemo(() => {
    if (!hhJsonParseResult.payload) {
      return { meFound: false, resumesMineFound: false, resumes: [] };
    }
    const payload = hhJsonParseResult.payload;
    const resumes = collectHhResumeCandidates(payload).map((item, index) => ({
      id: String(item.id ?? `json-resume-${index + 1}`),
      title: typeof item.title === 'string' && item.title.trim() ? item.title.trim() : `Resume ${index + 1}`,
      originalId: item.id ? String(item.id) : '',
    }));
    return {
      meFound: Boolean(payload.me && typeof payload.me === 'object'),
      resumesMineFound: Boolean(payload.resumes_mine && Array.isArray(payload.resumes_mine.items)),
      resumes,
    };
  }, [hhJsonParseResult]);

  const resolvedHhJsonResumeId = hhJsonResumeId || hhJsonPreview.resumes[0]?.id || '';
  const selectedHhJsonResume = hhJsonPreview.resumes.find((item) => item.id === resolvedHhJsonResumeId) ?? null;

  useEffect(() => {
    if (!hhJsonPreview.resumes.length) {
      setHhJsonResumeId('');
      return;
    }
    const hasSelected = hhJsonPreview.resumes.some((item) => item.id === hhJsonResumeId);
    if (!hasSelected) {
      setHhJsonResumeId(hhJsonPreview.resumes[0].id);
    }
  }, [hhJsonPreview, hhJsonResumeId]);

  function updateProfileField(name, value) {
    setProfile((current) => ({ ...current, [name]: value }));
  }

  async function saveProfile() {
    setProfileSaving(true);
    setToast('');
    setError('');

    let parsedTeamPreferences = {};
    try {
      parsedTeamPreferences = JSON.parse(teamPreferencesText || '{}');
      setTeamPreferencesError('');
    } catch {
      setTeamPreferencesError('Некорректный JSON.');
      setProfileSaving(false);
      return;
    }

    try {
      const payload = { ...profile, team_preferences_json: parsedTeamPreferences };
      const updated = await updateProfile(profileId, payload);
      setProfile(updated);
      setTeamPreferencesText(JSON.stringify(updated.team_preferences_json ?? {}, null, 2));
      setToast('Профиль сохранён.');
    } catch (requestError) {
      setError(requestError.message || 'Не удалось сохранить профиль.');
    } finally {
      setProfileSaving(false);
    }
  }

  function markSaving(key, value) {
    setSavingByKey((current) => ({ ...current, [key]: value }));
  }

  async function saveItem(section, item, ops) {
    const key = `${section}-${item.id ?? 'new'}`;
    markSaving(key, true);
    setError('');
    setToast('');

    const payload = Object.fromEntries(
      Object.entries(item).filter(([entryKey]) => !['id', 'profile_id', 'created_at', 'approved_at'].includes(entryKey)),
    );

    Object.keys(payload).forEach((entryKey) => {
      if (payload[entryKey] === '') {
        payload[entryKey] = null;
      }
    });

    try {
      const saved = item.id ? await ops.update(item.id, payload) : await ops.create(payload);
      ops.setItems((current) => {
        if (item.id) {
          return current.map((entry) => (entry.id === item.id ? saved : entry));
        }
        return [saved, ...current.filter((entry) => entry.id)];
      });
      setToast('Сохранено.');
    } catch (requestError) {
      setError(requestError.message || 'Не удалось сохранить запись.');
    } finally {
      markSaving(key, false);
    }
  }

  async function removeItem(section, id, ops) {
    const key = `${section}-${id}`;
    markSaving(key, true);
    try {
      await ops.remove(id);
      ops.setItems((current) => current.filter((entry) => entry.id !== id));
      setToast('Удалено.');
    } catch (requestError) {
      setError(requestError.message || 'Не удалось удалить запись.');
    } finally {
      markSaving(key, false);
    }
  }

  async function approveDoc(kind, id) {
    const key = `${kind}-${id}`;
    markSaving(key, true);
    try {
      const updater = kind === 'resumes' ? approveResumeVersion : approveCoverLetterVersion;
      const setItems = kind === 'resumes' ? setResumes : setLetters;
      const result = await updater(profileId, id);
      setItems((current) => current.map((entry) => (entry.id === id ? result : entry)));
      setToast('Версия подтверждена.');
    } catch (requestError) {
      setError(requestError.message || 'Не удалось подтвердить версию.');
    } finally {
      markSaving(key, false);
    }
  }

  async function runRecomputeAll() {
    try {
      await recomputeAllProfileData(profileId, DEFAULT_LIMIT);
      setToast('Пересчёт всего запущен.');
    } catch {
      setError('Endpoint /dev/profiles/{profile_id}/recompute-all недоступен.');
    }
  }

  function formatDateTime(value) {
    if (!value) {
      return '—';
    }
    return new Date(value).toLocaleString();
  }

  async function refreshHhBrowserStatus({ showSuccess = false } = {}) {
    setHhBrowserLoading(true);
    setHhBrowserError('');
    try {
      const status = await getHhBrowserConnectState();
      setHhBrowserStatus(status);
      if (showSuccess) {
        setHhBrowserMessage('Статус подключения HH обновлён.');
      }
    } catch {
      setHhBrowserError('Сервис HH временно недоступен. Обновите страницу или попробуйте позже.');
    } finally {
      setHhBrowserLoading(false);
    }
  }

  async function runHhBrowserAction(action, successMessage) {
    setHhBrowserBusy(true);
    setHhBrowserError('');
    setHhBrowserMessage('');
    try {
      const status = await action();
      setHhBrowserStatus(status);
      setHhBrowserMessage(successMessage);
    } catch (requestError) {
      setHhBrowserError(mapHhBrowserError(requestError));
    } finally {
      setHhBrowserBusy(false);
    }
  }

  function mapHhBrowserError(requestError) {
    const raw = String(requestError?.message ?? '');
    if (raw.includes('INVALID_CREDENTIALS')) {
      return 'Неверный логин или пароль HH. Проверьте данные и попробуйте снова.';
    }
    if (raw.includes('INVALID_CODE') || raw.includes('CODE_EXPIRED')) {
      return 'Код подтверждения неверный или устарел. Запросите новый код и повторите вход.';
    }
    if (raw.includes('SESSION_TIMEOUT')) {
      return 'Сессия подключения истекла. Нажмите «Подключить HH» и начните заново.';
    }
    if (raw.includes('UNRECOGNIZED_STATE')) {
      return 'Не удалось определить шаг входа HH. Попробуйте переподключить интеграцию.';
    }
    if (raw.includes('INVALID_TRANSITION')) {
      return 'Шаг устарел относительно состояния сервера. Обновите статус и продолжите.';
    }
    if (raw.includes('Failed to fetch') || raw.includes('502') || raw.includes('503') || raw.includes('504')) {
      return 'Backend HH недоступен. Повторите попытку чуть позже.';
    }
    return 'Подключение HH завершилось ошибкой. Повторите попытку.';
  }

  function mapHhSessionSafeError(status) {
    const errorCode = status?.last_error_code;
    if (!errorCode) {
      return '';
    }
    if (['TRANSIENT_NAVIGATION', 'TRANSIENT_WAIT', 'NETWORK_ERROR', 'SESSION_PROBE_UNAVAILABLE'].includes(errorCode)) {
      return 'Временная ошибка при проверке сессии HH. Это не означает выход из аккаунта — попробуйте снова.';
    }
    if (['SESSION_EXPIRED', 'SESSION_LOGGED_OUT', 'SESSION_REAUTH_REQUIRED', 'REAUTH_REQUIRED_MANUAL'].includes(errorCode)) {
      return 'Срок действия HH-сессии закончился. Нужна повторная авторизация через переподключение.';
    }
    if (['SESSION_STATE_NOT_FOUND', 'SESSION_STATE_CORRUPTED'].includes(errorCode)) {
      return 'Сохранённая сессия HH недоступна. Выполните переподключение, чтобы продолжить.';
    }
    if (errorCode === 'SESSION_STATE_MISSING') {
      return 'Серверная HH-сессия не найдена. Подключите HH заново.';
    }
    if (errorCode === 'INVALID_CREDENTIALS') {
      return 'Не удалось подтвердить вход HH. Проверьте логин/пароль и повторите подключение.';
    }
    if (errorCode === 'SESSION_TIMEOUT') {
      return 'Шаг входа HH устарел. Запустите подключение заново.';
    }
    return 'Не удалось подтвердить состояние HH-сессии. Попробуйте «Проверить сессию» или переподключение.';
  }

  async function startHhConnectWizard(forceRestart = false) {
    setHhBrowserError('');
    setHhBrowserMessage('');
    setHhPassword('');
    setHhCode('');
    await runHhBrowserAction(
      () => startHhBrowserConnection({ force_restart: forceRestart }),
      'Сессия HH запущена. Следуйте шагам ниже.',
    );
  }

  async function submitHhIdentifierForm(event) {
    event.preventDefault();
    setHhBrowserError('');
    setHhBrowserMessage('');
    await runHhBrowserAction(
      () => submitHhBrowserIdentifier({ identifier_type: hhIdentifierType, identifier: hhIdentifier.trim() }),
      'Логин отправлен в HH. Проверьте следующий шаг.',
    );
  }

  async function submitHhPasswordForm(event) {
    event.preventDefault();
    const passwordToSubmit = hhPassword;
    setHhPassword('');
    setHhBrowserError('');
    setHhBrowserMessage('');
    await runHhBrowserAction(
      () => submitHhBrowserPassword({ password: passwordToSubmit }),
      'Пароль отправлен. Если нужен код, появится следующий шаг.',
    );
  }

  async function submitHhCodeForm(event) {
    event.preventDefault();
    const codeToSubmit = hhCode;
    setHhCode('');
    setHhBrowserError('');
    setHhBrowserMessage('');
    await runHhBrowserAction(
      () => submitHhBrowserCode({ code: codeToSubmit }),
      'Код подтверждения отправлен. Проверяем результат.',
    );
  }

  async function connectHh() {
    setHhBusy(true);
    setError('');
    try {
      const response = await startHhOAuthConnect();
      window.location.href = response.authorize_url;
    } catch (requestError) {
      setError(requestError.message || 'Не удалось начать подключение HH.');
      setHhBusy(false);
    }
  }

  async function importFromHh() {
    setHhBusy(true);
    setError('');
    setToast('');
    try {
      await importProfileFromHh({ consent: true, resume_id: hhResumeId || null });
      await refreshAfterImport();
      setToast('Профиль импортирован из HH.');
    } catch (requestError) {
      setError(requestError.message || 'Импорт HH завершился с ошибкой.');
    } finally {
      setHhBusy(false);
    }
  }

  async function disconnectFromHh() {
    setHhBusy(true);
    setError('');
    try {
      await disconnectHh();
      setHhStatus({ connected: false });
      setHhResumes([]);
      setHhResumeId('');
      setToast('HH отключён.');
    } catch (requestError) {
      setError(requestError.message || 'Не удалось отключить HH.');
    } finally {
      setHhBusy(false);
    }
  }

  function collectHhResumeCandidates(payload) {
    const candidates = [];
    if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
      return candidates;
    }

    if (payload.resume && typeof payload.resume === 'object' && !Array.isArray(payload.resume)) {
      candidates.push(payload.resume);
    }

    if (Array.isArray(payload.resumes)) {
      candidates.push(...payload.resumes.filter((item) => item && typeof item === 'object' && !Array.isArray(item)));
    }

    if (payload.resumes_mine && typeof payload.resumes_mine === 'object' && Array.isArray(payload.resumes_mine.items)) {
      candidates.push(...payload.resumes_mine.items.filter((item) => item && typeof item === 'object' && !Array.isArray(item)));
    }

    const looksLikeResume = ['id', 'title', 'first_name', 'last_name', 'experience', 'skill_set', 'description', 'contact']
      .some((key) => key in payload);
    if (looksLikeResume) {
      candidates.push(payload);
    }

    const deduped = [];
    const seen = new Set();
    candidates.forEach((candidate, index) => {
      const signature = String(candidate.id ?? `idx-${index}`);
      if (seen.has(signature)) {
        return;
      }
      seen.add(signature);
      deduped.push(candidate);
    });
    return deduped;
  }

  function formatHhJsonError(requestError, fallbackMessage) {
    if (!requestError) {
      return fallbackMessage;
    }
    if (typeof requestError.message === 'string' && requestError.message.trim()) {
      return requestError.message;
    }
    if (typeof requestError.detail === 'string' && requestError.detail.trim()) {
      return requestError.detail;
    }
    return fallbackMessage;
  }

  function formatApiError(requestError, fallbackMessage) {
    if (!requestError?.message) {
      return fallbackMessage;
    }

    const detailMatch = String(requestError.message).match(/\):\s*(.+)$/);
    return detailMatch?.[1] || String(requestError.message) || fallbackMessage;
  }

  function onResumeImportFileChange(event) {
    const [file] = event.target.files ?? [];
    setResumeImportFile(file ?? null);
    setResumeImportParseError('');
    setResumeImportApplyError('');
    setResumeImportExtractionWarnings([]);
    setResumeImportExtractedTextLength(0);
    setResumeImportExtractedFileName(file?.name ?? '');
    setResumeImportDraftResponse(null);
    setResumeImportApplySummary(null);
  }

  async function extractAndParseResumeFile() {
    if (!resumeImportFile) {
      setResumeImportParseError('Выберите файл резюме перед запуском импорта.');
      return;
    }

    const extension = resumeImportFile.name.includes('.')
      ? resumeImportFile.name.split('.').pop().toLowerCase()
      : '';
    if (!SUPPORTED_RESUME_IMPORT_EXTENSIONS.includes(extension)) {
      setResumeImportParseError('Неподдерживаемый формат файла. Разрешены: txt, md, docx, pdf, rtf.');
      return;
    }

    setResumeImportBusy(true);
    setResumeImportParseError('');
    setResumeImportApplyError('');
    setResumeImportApplySummary(null);
    setResumeImportDraftResponse(null);
    setResumeImportExtractionWarnings([]);
    setResumeImportExtractedTextLength(0);
    setResumeImportExtractedFileName(resumeImportFile.name);
    setToast('');
    setError('');

    try {
      const extractionResult = await extractResumeImportFile(profileId, resumeImportFile);
      setResumeImportExtractionWarnings(extractionResult.warnings ?? []);
      setResumeImportExtractedTextLength(extractionResult.text_length ?? 0);

      const parseResult = await parseResumeImportText(profileId, extractionResult.extracted_text);
      setResumeImportDraftResponse(parseResult);
    } catch (requestError) {
      setResumeImportParseError(
        formatApiError(requestError, 'Не удалось извлечь или распарсить данные резюме.'),
      );
    } finally {
      setResumeImportBusy(false);
    }
  }

  async function applyResumeImportToProfile() {
    if (!resumeImportDraftResponse?.draft) {
      setResumeImportApplyError('Сначала получите черновик из файла резюме.');
      return;
    }

    const hasUsefulContent = Boolean(resumeImportDraftResponse.applyability?.has_useful_content);
    if (!hasUsefulContent) {
      setResumeImportApplyError('Черновик содержит недостаточно данных для импорта в профиль.');
      return;
    }

    setResumeImportBusy(true);
    setResumeImportApplyError('');
    setToast('');
    setError('');

    try {
      const result = await applyResumeImportDraft(profileId, {
        draft: resumeImportDraftResponse.draft,
        update_main_fields: true,
        replace_sections: ['experiences', 'skills', 'languages', 'links'],
      });
      setResumeImportApplySummary({
        ...result,
        imported_file_name: resumeImportExtractedFileName || resumeImportFile?.name || '',
        applied_at: new Date().toISOString(),
      });
      await refreshAfterImport();
      setToast('Импорт из файла применён к профилю.');
    } catch (requestError) {
      setResumeImportApplyError(
        formatApiError(requestError, 'Не удалось применить импортированные данные к профилю.'),
      );
    } finally {
      setResumeImportBusy(false);
    }
  }

  async function refreshAfterImport() {
    const [
      profileData,
      experiencesData,
      skillsData,
      languagesData,
      linksData,
      statusData,
    ] = await Promise.all([
      getProfile(profileId),
      listExperiences(profileId),
      listSkills(profileId),
      listLanguages(profileId),
      listLinks(profileId),
      getHhConnectionStatus(),
    ]);

    setProfile(profileData);
    setExperiences(experiencesData.sort((a, b) => (a.start_date < b.start_date ? 1 : -1)));
    setSkills(skillsData);
    setLanguages(languagesData);
    setLinks(linksData);
    setHhStatus(statusData);
  }

  function onHhJsonFileUpload(event) {
    const [file] = event.target.files ?? [];
    if (!file) {
      return;
    }

    setHhJsonError('');
    setHhJsonImportSummary(null);

    if (!file.name.toLowerCase().endsWith('.json')) {
      setHhJsonError('Выберите файл с расширением .json.');
      return;
    }

    const reader = new FileReader();
    reader.onload = () => {
      const content = typeof reader.result === 'string' ? reader.result : '';
      setHhJsonRaw(content);
    };
    reader.onerror = () => {
      setHhJsonError('Не удалось прочитать файл JSON.');
    };
    reader.readAsText(file, 'utf-8');
  }

  async function importFromHhJson() {
    setHhJsonBusy(true);
    setHhJsonError('');
    setError('');
    setToast('');
    setHhJsonImportSummary(null);

    try {
      if (!hhJsonConsent) {
        throw new Error('Подтвердите согласие на импорт данных из локального JSON.');
      }

      if (!hhJsonRaw.trim()) {
        throw new Error('Загрузите файл JSON или вставьте JSON в поле ниже.');
      }

      let parsedPayload;
      try {
        parsedPayload = JSON.parse(hhJsonRaw);
      } catch {
        throw new Error('Некорректный JSON: проверьте синтаксис.');
      }

      const previewCandidates = collectHhResumeCandidates(parsedPayload);
      if (!previewCandidates.length) {
        throw new Error('В JSON не найдено резюме. Ожидается HH-like payload с resumes/resumes_mine.');
      }

      const selectedPreviewResume = hhJsonPreview.resumes.find((item) => item.id === resolvedHhJsonResumeId) ?? null;
      const selectedResumeId = selectedPreviewResume?.originalId || null;
      const result = await importProfileFromHhJson({
        consent: true,
        payload: parsedPayload,
        resume_id: selectedResumeId,
      });

      await refreshAfterImport();
      setHhJsonImportSummary(result);
      setToast('Профиль импортирован из локального HH-like JSON.');
    } catch (requestError) {
      setHhJsonError(formatHhJsonError(requestError, 'Импорт из JSON завершился с ошибкой.'));
    } finally {
      setHhJsonBusy(false);
    }
  }

  function buildTargetedResumePayload({ dryRun }) {
    return {
      profile_id: profileId,
      vacancy_id: targetVacancyId ? Number(targetVacancyId) : null,
      source_resume_version_id: targetResumeVersionId ? Number(targetResumeVersionId) : null,
      target_title: targetTitle.trim() || null,
      summary: targetSummary.trim() || null,
      skills_focus: normalizedSkillsFocus,
      include_skill_levels: targetIncludeSkillLevels,
      max_experiences: Math.max(1, Math.min(10, Number(targetMaxExperiences) || 4)),
      do_not_hide_from_all_employers: targetDoNotHideFromAllEmployers,
      dry_run: dryRun,
    };
  }

  function mapTargetedResumeError(requestError) {
    const raw = String(requestError?.message ?? '');
    if (raw.includes('Active HH browser session required')) {
      return 'Нет активной HH-сессии. Переподключите HH и повторите.';
    }
    if (raw.includes('Vacancy not found')) {
      return 'Выбранная вакансия не найдена. Обновите страницу и выберите вакансию снова.';
    }
    if (raw.includes('Resume version not found')) {
      return 'Выбранная версия внутреннего резюме не найдена.';
    }
    if (raw.includes('another profile')) {
      return 'Источник резюме принадлежит другому профилю. Выберите верную версию.';
    }
    if (raw.includes('Failed to fetch') || raw.includes('502') || raw.includes('503') || raw.includes('504')) {
      return 'Сервис HH временно недоступен. Повторите попытку позже.';
    }
    return formatApiError(requestError, 'Не удалось создать targeted HH-резюме.');
  }

  function mapVisibilityActionError(requestError) {
    const raw = String(requestError?.message ?? '');
    if (raw.includes('Active HH browser session required')) {
      return 'Нет активной HH-сессии. Переподключите HH и повторите действие.';
    }
    if (raw.includes('not found')) {
      return 'Не удалось найти managed HH-резюме. Обновите список и попробуйте снова.';
    }
    if (raw.includes('Failed to fetch') || raw.includes('502') || raw.includes('503') || raw.includes('504')) {
      return 'Сервис HH временно недоступен. Повторите попытку позже.';
    }
    return formatApiError(requestError, 'Операция с видимостью HH-резюме завершилась ошибкой.');
  }

  async function refreshManagedResumesList() {
    try {
      const items = await listHhManagedResumes();
      setHhManagedResumes(items);
    } catch {
      setHhTargetError('Не удалось обновить список локально отслеживаемых HH-резюме.');
    }
  }

  function updateManagedResumeVisibilityLocally(managedResumeId, visibilityPayload) {
    setHhManagedResumes((current) => current.map((item) => {
      if (item.id !== managedResumeId) {
        return item;
      }
      return {
        ...item,
        desired_visibility_mode: visibilityPayload.desired_visibility_mode ?? item.desired_visibility_mode,
        current_visibility_mode: visibilityPayload.current_visibility_mode ?? item.current_visibility_mode,
        visibility_last_checked_at: visibilityPayload.visibility_last_checked_at ?? item.visibility_last_checked_at,
        visibility_last_changed_at: visibilityPayload.visibility_last_changed_at ?? item.visibility_last_changed_at,
        visibility_status: visibilityPayload.visibility_status ?? item.visibility_status,
        visibility_error_code: visibilityPayload.visibility_error_code ?? null,
        visibility_error_message: visibilityPayload.visibility_error_message ?? null,
      };
    }));
  }

  async function runManagedVisibilityAction({ managedResumeId, action, successMessage }) {
    setHhVisibilityError('');
    setHhVisibilityMessage('');
    setHhVisibilityBusyById((current) => ({ ...current, [managedResumeId]: true }));
    try {
      const visibility = await action(managedResumeId);
      updateManagedResumeVisibilityLocally(managedResumeId, visibility);
      setHhVisibilityMessage(successMessage);
      await refreshManagedResumesList();
      await refreshHhBrowserStatus();
    } catch (requestError) {
      setHhVisibilityError(mapVisibilityActionError(requestError));
    } finally {
      setHhVisibilityBusyById((current) => ({ ...current, [managedResumeId]: false }));
    }
  }

  async function runTargetedPreview() {
    setHhTargetBusy(true);
    setHhTargetError('');
    setHhTargetMessage('');
    setHhTargetLastResult(null);
    try {
      const response = await createHhTargetedResume(buildTargetedResumePayload({ dryRun: true }));
      setHhTargetPreview(response.payload_preview ?? null);
      setHhTargetMessage('Preview обновлён. Можно запускать создание HH-резюме.');
      await refreshManagedResumesList();
    } catch (requestError) {
      setHhTargetError(mapTargetedResumeError(requestError));
    } finally {
      setHhTargetBusy(false);
    }
  }

  async function runTargetedCreate() {
    setHhTargetBusy(true);
    setHhTargetError('');
    setHhTargetMessage('');
    setHhTargetLastResult(null);
    try {
      const response = await createHhTargetedResume(buildTargetedResumePayload({ dryRun: false }));
      const managedResume = response.managed_resume ?? null;
      const autoHideEnabled = managedResume?.auto_hide_from_all_enabled !== false;
      setHhTargetLastResult(managedResume);
      setHhTargetMessage(
        autoHideEnabled
          ? 'Создание HH-резюме завершено. По умолчанию резюме будет скрываться от всех работодателей.'
          : 'Создание HH-резюме завершено. Автоскрытие отключено: резюме не будет принудительно скрываться от всех.',
      );
      await refreshManagedResumesList();
      await refreshHhBrowserStatus();
    } catch (requestError) {
      setHhTargetError(mapTargetedResumeError(requestError));
    } finally {
      setHhTargetBusy(false);
    }
  }

  const experienceOptions = useMemo(
    () => experiences.map((item) => ({ value: String(item.id), label: `${item.company_name} — ${item.position_title}` })),
    [experiences],
  );

  const projectOptions = useMemo(
    () => projects.map((item) => ({ value: String(item.id), label: item.name })),
    [projects],
  );
  const vacancyOptions = useMemo(
    () => vacancies.map((item) => ({ value: String(item.id), label: `${item.title} (${item.company_name || 'Компания не указана'})` })),
    [vacancies],
  );
  const targetResumeOptions = useMemo(
    () => resumes.map((item) => ({ value: String(item.id), label: `${item.title || `Resume #${item.id}`} (${item.status})` })),
    [resumes],
  );
  const managedResumeRows = useMemo(
    () => hhManagedResumes.map((item) => ({
      ...item,
      vacancy: vacancies.find((vacancy) => vacancy.id === item.vacancy_id) ?? null,
      sourceResume: resumes.find((resume) => resume.id === item.source_resume_version_id) ?? null,
      statusMeta: HH_MANAGED_RESUME_STATUS_META[item.status] ?? { label: item.status, tone: 'neutral' },
      visibilityModeMeta: HH_VISIBILITY_MODE_META[item.current_visibility_mode] ?? { label: item.current_visibility_mode || '—', tone: 'neutral' },
      visibilityStatusMeta: HH_VISIBILITY_STATUS_META[item.visibility_status] ?? { label: item.visibility_status || '—', tone: 'neutral' },
    })),
    [hhManagedResumes, resumes, vacancies],
  );

  const visibleResumes = approvedOnlyResume ? resumes.filter((item) => item.status === 'approved') : resumes;
  const visibleLetters = approvedOnlyLetter ? letters.filter((item) => item.status === 'approved') : letters;
  const hhBrowserStatusMeta = HH_BROWSER_STATUS_META[hhBrowserStatus?.status] ?? {
    label: hhBrowserStatus?.status || 'Unknown',
    tone: 'neutral',
  };
  const hhBrowserHealthMeta = HH_BROWSER_SESSION_HEALTH_META[hhBrowserStatus?.status] ?? {
    title: 'Статус сессии обновляется',
    text: 'Проверьте состояние HH-сессии позже.',
    tone: 'neutral',
  };
  const hhBrowserSafeError = mapHhSessionSafeError(hhBrowserStatus);
  const showReauthCta = hhBrowserStatus?.requires_reauth || hhBrowserStatus?.status === 'failed';
  const showRestoreAction = hhBrowserStatus?.status === 'disconnected' && !hhBrowserStatus?.session_present;
  const showCheckSessionAction = ['connected', 'requires_reauth', 'failed'].includes(hhBrowserStatus?.status);
  const hhSessionActive = hhBrowserStatus?.status === 'connected' && hhBrowserStatus?.session_present && !hhBrowserStatus?.requires_reauth;
  const selectedTargetVacancy = vacancies.find((item) => String(item.id) === targetVacancyId) ?? null;
  const selectedTargetResumeVersion = resumes.find((item) => String(item.id) === targetResumeVersionId) ?? null;
  const normalizedSkillsFocus = targetSkillsFocusRaw
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean);
  const targetedPreviewSummary = useMemo(() => ({
    targetTitle: targetTitle.trim() || selectedTargetVacancy?.title || profile.title || 'Специалист',
    sourceProfile: profile.full_name || profile.title || `profile_id=${profileId}`,
    sourceResumeTitle: selectedTargetResumeVersion?.title || 'Не выбран',
    selectedSkillsCount: normalizedSkillsFocus.length || skills.length,
    experiencesCount: Math.min(Number(targetMaxExperiences) || 4, experiences.length),
    vacancyContext: selectedTargetVacancy ? `${selectedTargetVacancy.title} · ${selectedTargetVacancy.company_name || '—'}` : 'Без вакансии',
  }), [
    experiences.length,
    normalizedSkillsFocus.length,
    profile.full_name,
    profile.title,
    profileId,
    selectedTargetResumeVersion?.title,
    selectedTargetVacancy,
    skills.length,
    targetMaxExperiences,
    targetTitle,
  ]);
  const isTransientSessionIssue = ['TRANSIENT_NAVIGATION', 'TRANSIENT_WAIT', 'NETWORK_ERROR', 'SESSION_PROBE_UNAVAILABLE'].includes(
    hhBrowserStatus?.last_error_code,
  );
  const profileCompleteness = useMemo(() => {
    const points = [
      Boolean(profile.full_name),
      Boolean(profile.title),
      Boolean(profile.summary_about),
      experiences.length > 0,
      skills.length > 0,
      resumes.length > 0,
    ];
    return Math.round((points.filter(Boolean).length / points.length) * 100);
  }, [experiences.length, profile.full_name, profile.summary_about, profile.title, resumes.length, skills.length]);

  if (loading) {
    return <Loading message="Загрузка /settings..." />;
  }

  return (
    <section className="page-stack">
      <header className="product-page-header">
        <div>
          <p className="product-page-header__eyebrow">Profile workspace</p>
          <h1>{`Settings (profile_id=${profileId})`}</h1>
          <p className="product-page-header__subtitle">Управляйте профилем, документами и интеграциями в едином рабочем модуле.</p>
        </div>
      </header>
      {error ? <ErrorBanner message={error} /> : null}
      {toast ? <p className="success-banner">{toast}</p> : null}

      <section className="applications-summary">
        <article><p>Профиль</p><strong>{profileCompleteness}%</strong></article>
        <article><p>Skills</p><strong>{skills.length}</strong></article>
        <article><p>Experience</p><strong>{experiences.length}</strong></article>
        <article><p>Resume versions</p><strong>{resumes.length}</strong></article>
        <article><p>Cover letters</p><strong>{letters.length}</strong></article>
      </section>

      <div className="recommendations-toolbar">
        <button className="button" type="button" onClick={() => recomputeRecommendations(profileId, DEFAULT_LIMIT)}>
          Пересчитать рекомендации
        </button>
        <button className="button button--ghost" type="button" onClick={runRecomputeAll}>
          Пересчитать всё
        </button>
        <Link to="/recommendations" className="button button--ghost">Перейти к рекомендациям</Link>
      </div>

      <Section title="Интеграция HH через браузерную сессию" defaultOpen>
        <p className="muted-text">
          Подключение выполняется через живую браузерную сессию HH. Это не OAuth-поток: вы проходите стандартные шаги входа HH.
        </p>
        <p className="muted-text">Пароль и код подтверждения используются только для текущего шага и не сохраняются в хранилище приложения.</p>
        <p className="muted-text">После успешного входа используется серверная HH-сессия для дальнейших операций.</p>
        {hhBrowserLoading ? <Loading message="Обновляем HH Browser статус..." /> : null}
        {hhBrowserError ? <ErrorBanner message={hhBrowserError} /> : null}
        {hhBrowserMessage ? <p className="success-banner">{hhBrowserMessage}</p> : null}
        <p>
          <strong>{hhBrowserHealthMeta.title}.</strong>{' '}
          {hhBrowserHealthMeta.text}
        </p>
        {isTransientSessionIssue ? (
          <p className="muted-text">Сбой выглядит временным. Сессия может быть активной — запустите повторную проверку.</p>
        ) : null}

        <div className="settings-grid settings-grid--two">
          <p>
            <strong>Статус:</strong>{' '}
            <span className={`applications-status-chip applications-status-chip--${hhBrowserStatusMeta.tone}`}>
              {hhBrowserStatusMeta.label}
            </span>
          </p>
          <p><strong>Серверная сессия:</strong> {hhBrowserStatus?.session_present ? 'Есть' : 'Нет'}</p>
          <p><strong>Нужна повторная авторизация:</strong> {hhBrowserStatus?.requires_reauth ? 'Да' : 'Нет'}</p>
          <p><strong>Последняя авторизация:</strong> {formatDateTime(hhBrowserStatus?.last_authenticated_at)}</p>
          <p><strong>Последняя проверка:</strong> {formatDateTime(hhBrowserStatus?.last_checked_at)}</p>
          <p><strong>Сообщение:</strong> {hhBrowserSafeError || '—'}</p>
        </div>

        <div className="recommendations-toolbar">
          <button
            className="button"
            type="button"
            onClick={() => startHhConnectWizard(false)}
            disabled={hhBrowserBusy || hhBrowserLoading}
          >
            {hhBrowserBusy ? 'Обновление...' : 'Подключить HH'}
          </button>
          {showReauthCta ? (
            <button
              className="button"
              type="button"
              onClick={() => startHhConnectWizard(true)}
              disabled={hhBrowserBusy || hhBrowserLoading}
            >
              Переподключить HH
            </button>
          ) : null}
          {showCheckSessionAction ? (
            <button
              className="button button--ghost"
              type="button"
              onClick={() => runHhBrowserAction(checkHhBrowserSession, 'Проверка HH-сессии завершена.')}
              disabled={hhBrowserBusy || hhBrowserLoading}
            >
              Проверить сессию
            </button>
          ) : null}
          {showRestoreAction ? (
            <button
              className="button button--ghost"
              type="button"
              onClick={() => runHhBrowserAction(restoreHhBrowserSession, 'Пробуем восстановить HH-сессию.')}
              disabled={hhBrowserBusy || hhBrowserLoading}
            >
              Восстановить сессию
            </button>
          ) : null}
          <button
            className="button button--ghost button--danger"
            type="button"
            onClick={() => runHhBrowserAction(disconnectHhBrowserConnection, 'HH отключён.')}
            disabled={hhBrowserBusy || hhBrowserLoading}
          >
            Отключить HH
          </button>
          <button
            className="button button--ghost"
            type="button"
            onClick={() => refreshHhBrowserStatus({ showSuccess: true })}
            disabled={hhBrowserBusy || hhBrowserLoading}
          >
            Обновить статус
          </button>
          <button
            className="button button--ghost"
            type="button"
            onClick={() => runHhBrowserAction(cancelHhBrowserConnection, 'Текущий шаг подключения отменён.')}
            disabled={hhBrowserBusy || hhBrowserLoading}
          >
            Отмена
          </button>
        </div>

        {hhBrowserStatus?.status === 'awaiting_identifier' ? (
          <form className="settings-grid settings-grid--two" onSubmit={submitHhIdentifierForm}>
            <SelectField
              label="Тип логина"
              value={hhIdentifierType}
              onChange={(event) => setHhIdentifierType(event.target.value)}
              options={[
                { value: 'phone', label: 'Телефон' },
                { value: 'email', label: 'Email' },
              ]}
            />
            <TextField
              label={hhIdentifierType === 'phone' ? 'Телефон HH' : 'Email HH'}
              value={hhIdentifier}
              onChange={(event) => setHhIdentifier(event.target.value)}
              placeholder={hhIdentifierType === 'phone' ? '+7...' : 'name@example.com'}
            />
            <div className="recommendations-toolbar">
              <button className="button" type="submit" disabled={hhBrowserBusy || !hhIdentifier.trim()}>
                Продолжить
              </button>
            </div>
          </form>
        ) : null}

        {hhBrowserStatus?.status === 'awaiting_password' ? (
          <form className="settings-grid settings-grid--two" onSubmit={submitHhPasswordForm}>
            <TextField
              label="Пароль HH"
              type="password"
              autoComplete="current-password"
              value={hhPassword}
              onChange={(event) => setHhPassword(event.target.value)}
              placeholder="Введите пароль HH"
            />
            <div className="recommendations-toolbar">
              <button className="button" type="submit" disabled={hhBrowserBusy || !hhPassword}>
                Отправить пароль
              </button>
            </div>
          </form>
        ) : null}

        {hhBrowserStatus?.status === 'awaiting_code' ? (
          <form className="settings-grid settings-grid--two" onSubmit={submitHhCodeForm}>
            <TextField
              label="Код подтверждения"
              value={hhCode}
              onChange={(event) => setHhCode(event.target.value)}
              placeholder="Код из SMS/приложения"
            />
            <div className="recommendations-toolbar">
              <button className="button" type="submit" disabled={hhBrowserBusy || !hhCode.trim()}>
                Подтвердить код
              </button>
            </div>
          </form>
        ) : null}

        {hhBrowserStatus?.status === 'connected' ? (
          <p className="muted-text">
            HH подключён. Сессия активна на сервере и готова к работе.
          </p>
        ) : null}

        {hhBrowserStatus?.status === 'failed' || hhBrowserStatus?.status === 'requires_reauth' ? (
          <p className="muted-text">
            Текущая HH-сессия больше не подходит. Нажмите «Переподключить HH», чтобы пройти вход заново.
          </p>
        ) : null}
      </Section>

      <Section title="Targeted HH-резюме (MVP foundation)" defaultOpen>
        <p className="muted-text">
          Этот экран покрывает безопасный MVP: создание targeted HH-резюме + проверка текущей видимости + действие «Скрыть от всех».
        </p>
        <p className="muted-text">
          Важно: по умолчанию новое HH-резюме на HH может быть видно работодателям. Для точечного резюме рекомендуем сразу применить «Скрыть от всех».
        </p>
        {!hhSessionActive ? (
          <div className="error-banner">
            <p><strong>Нужна активная HH browser session.</strong> Без неё создание targeted HH-резюме недоступно.</p>
            <button
              className="button"
              type="button"
              onClick={() => startHhConnectWizard(true)}
              disabled={hhTargetBusy || hhBrowserBusy || hhBrowserLoading}
            >
              Переподключить HH
            </button>
          </div>
        ) : null}
        {hhTargetError ? <ErrorBanner message={hhTargetError} /> : null}
        {hhTargetMessage ? <p className="success-banner">{hhTargetMessage}</p> : null}
        <div className="settings-grid settings-grid--two">
          <SelectField
            label="Вакансия (опционально)"
            value={targetVacancyId}
            onChange={(event) => setTargetVacancyId(event.target.value)}
            options={[{ value: '', label: 'Без привязки к вакансии' }, ...vacancyOptions]}
          />
          <SelectField
            label="Источник: версия внутреннего резюме (опционально)"
            value={targetResumeVersionId}
            onChange={(event) => setTargetResumeVersionId(event.target.value)}
            options={[{ value: '', label: 'Использовать профиль без конкретной версии' }, ...targetResumeOptions]}
          />
          <TextField
            label="Target title (опционально)"
            value={targetTitle}
            onChange={(event) => setTargetTitle(event.target.value)}
            placeholder={selectedTargetVacancy?.title || profile.title || 'Например, Backend Engineer'}
          />
          <TextField
            label="Skills focus (через запятую)"
            value={targetSkillsFocusRaw}
            onChange={(event) => setTargetSkillsFocusRaw(event.target.value)}
            placeholder="Python, FastAPI, PostgreSQL"
          />
          <TextField
            label="Максимум experiences в HH"
            type="number"
            value={targetMaxExperiences}
            onChange={(event) => setTargetMaxExperiences(event.target.value)}
            min={1}
            max={10}
          />
          <SwitchField
            label="Добавлять hints по уровню навыков"
            checked={targetIncludeSkillLevels}
            onChange={(event) => setTargetIncludeSkillLevels(event.target.checked)}
          />
        </div>
        <TextAreaField
          label="Summary override (опционально)"
          rows={3}
          value={targetSummary}
          onChange={(event) => setTargetSummary(event.target.value)}
          placeholder="Если оставить пустым, summary будет собрано из профиля + внутреннего резюме + контекста вакансии."
        />
        <article className="hh-targeted-preview-card">
          <h3 className="hh-targeted-preview-card__title">Preview перед запуском</h3>
          <SwitchField
            label="Не скрывать от всех работодателей"
            checked={targetDoNotHideFromAllEmployers}
            onChange={(event) => setTargetDoNotHideFromAllEmployers(event.target.checked)}
          />
          <p className="muted-text">
            По умолчанию мы скроем это HH-резюме от всех работодателей. При отклике нужный работодатель всё равно увидит резюме.
            Если включить чекбокс, автоскрытие от всех работодателей отключается.
          </p>
          <ul className="hh-targeted-preview-list">
            <li><strong>Target title:</strong> {targetedPreviewSummary.targetTitle}</li>
            <li><strong>Source profile:</strong> {targetedPreviewSummary.sourceProfile}</li>
            <li><strong>Source internal resume version:</strong> {targetedPreviewSummary.sourceResumeTitle}</li>
            <li><strong>Selected/highlighted skills:</strong> {targetedPreviewSummary.selectedSkillsCount}</li>
            <li><strong>Experiences:</strong> {targetedPreviewSummary.experiencesCount}</li>
            <li><strong>Vacancy context:</strong> {targetedPreviewSummary.vacancyContext}</li>
          </ul>
          {hhTargetPreview ? (
            <p className="muted-text">
              Dry-run preview: skills={hhTargetPreview.skills?.length ?? 0}, experiences={hhTargetPreview.work_experience?.length ?? 0},
              emphasis={hhTargetPreview.targeted_emphasis?.length ?? 0}.
            </p>
          ) : null}
          <div className="recommendations-toolbar">
            <button
              className="button button--ghost"
              type="button"
              onClick={runTargetedPreview}
              disabled={!hhSessionActive || hhTargetBusy}
            >
              {hhTargetBusy ? 'Готовим preview...' : 'Обновить preview (dry-run)'}
            </button>
            <button
              className="button"
              type="button"
              onClick={runTargetedCreate}
              disabled={!hhSessionActive || hhTargetBusy}
            >
              {hhTargetBusy ? 'Создаём HH-резюме...' : 'Создать HH-резюме'}
            </button>
          </div>
        </article>
        {hhTargetLastResult ? (
          <article className="editor-card">
            <h3 className="hh-targeted-preview-card__title">Результат последнего запуска</h3>
            <p><strong>HH resume title:</strong> {hhTargetLastResult.title || '—'}</p>
            <p>
              <strong>Status:</strong>{' '}
              <span className={`applications-status-chip applications-status-chip--${HH_MANAGED_RESUME_STATUS_META[hhTargetLastResult.status]?.tone || 'neutral'}`}>
                {HH_MANAGED_RESUME_STATUS_META[hhTargetLastResult.status]?.label || hhTargetLastResult.status}
              </span>
            </p>
            <p><strong>External URL:</strong> {hhTargetLastResult.hh_resume_url ? <a href={hhTargetLastResult.hh_resume_url} target="_blank" rel="noreferrer">Открыть на HH</a> : '—'}</p>
            <p><strong>Created:</strong> {formatDateTime(hhTargetLastResult.created_at)}</p>
            <p><strong>Updated:</strong> {formatDateTime(hhTargetLastResult.updated_at)}</p>
            <p className="muted-text">
              Рекомендуемый безопасный шаг: сразу проверьте visibility и при необходимости нажмите «Скрыть от всех» в списке tracked HH-резюме ниже.
            </p>
          </article>
        ) : null}

        <article className="editor-card">
          <div className="editor-card__header">
            <h3 className="hh-targeted-preview-card__title">Локально отслеживаемые HH managed resumes</h3>
            <button className="button button--ghost button--sm" type="button" onClick={refreshManagedResumesList} disabled={hhTargetBusy}>
              Обновить список
            </button>
          </div>
          {hhVisibilityError ? <ErrorBanner message={hhVisibilityError} /> : null}
          {hhVisibilityMessage ? <p className="success-banner">{hhVisibilityMessage}</p> : null}
          {!managedResumeRows.length ? <p className="muted-text">Пока нет tracked HH managed resumes.</p> : null}
          {managedResumeRows.length ? (
            <div className="hh-managed-table-wrap">
              <table className="hh-managed-table">
                <thead>
                  <tr>
                    <th>Title</th>
                    <th>Vacancy context</th>
                    <th>Source resume version</th>
                    <th>Status</th>
                    <th>Visibility</th>
                    <th>Updated</th>
                    <th>Actions</th>
                    <th>HH link</th>
                  </tr>
                </thead>
                <tbody>
                  {managedResumeRows.map((item) => (
                    <tr key={item.id}>
                      <td>{item.title || `Managed #${item.id}`}</td>
                      <td>
                        {item.vacancy ? <Link to={`/vacancies/${item.vacancy.id}`}>{item.vacancy.title}</Link> : '—'}
                      </td>
                      <td>{item.sourceResume?.title || '—'}</td>
                      <td>
                        <span className={`applications-status-chip applications-status-chip--${item.statusMeta.tone}`}>
                          {item.statusMeta.label}
                        </span>
                      </td>
                      <td>
                        <p>
                          <span className={`applications-status-chip applications-status-chip--${item.visibilityModeMeta.tone}`}>
                            {item.visibilityModeMeta.label}
                          </span>
                        </p>
                        <p className="muted-text">
                          Статус:{' '}
                          <span className={`applications-status-chip applications-status-chip--${item.visibilityStatusMeta.tone}`}>
                            {item.visibilityStatusMeta.label}
                          </span>
                        </p>
                        <p className="muted-text">
                          <strong>Privacy policy:</strong>{' '}
                          {item.auto_hide_from_all_enabled !== false ? 'Скрываем от всех по умолчанию' : 'Автоскрытие отключено'}
                        </p>
                        <p className="muted-text">
                          <strong>Preference:</strong>{' '}
                          {item.auto_hide_from_all_enabled !== false ? 'auto-hide enabled' : 'opt-out'}
                        </p>
                        <p className="muted-text"><strong>Проверка:</strong> {formatDateTime(item.visibility_last_checked_at)}</p>
                        <p className="muted-text"><strong>Изменение:</strong> {formatDateTime(item.visibility_last_changed_at)}</p>
                        {item.visibility_error_message ? <p className="muted-text"><strong>Ошибка:</strong> {item.visibility_error_message}</p> : null}
                        {item.current_visibility_mode === 'unknown' ? <p className="muted-text">Сначала проверьте видимость.</p> : null}
                        {item.current_visibility_mode === 'hidden_from_all' ? <p className="muted-text">Безопасный режим уже включён.</p> : null}
                      </td>
                      <td>{formatDateTime(item.updated_at)}</td>
                      <td>
                        {!hhSessionActive ? (
                          <div className="settings-grid">
                            <p className="muted-text">Нет активной HH-сессии.</p>
                            <button
                              className="button button--ghost button--sm"
                              type="button"
                              onClick={() => startHhConnectWizard(true)}
                              disabled={hhTargetBusy || hhBrowserBusy || hhBrowserLoading}
                            >
                              Переподключить HH
                            </button>
                          </div>
                        ) : (
                          <div className="settings-grid">
                            <button
                              className="button button--ghost button--sm"
                              type="button"
                              onClick={() => runManagedVisibilityAction({
                                managedResumeId: item.id,
                                action: checkHhManagedResumeVisibility,
                                successMessage: 'Видимость HH-резюме обновлена.',
                              })}
                              disabled={hhTargetBusy || hhVisibilityBusyById[item.id]}
                            >
                              {hhVisibilityBusyById[item.id] ? 'Проверяем...' : 'Проверить видимость'}
                            </button>
                            <button
                              className="button button--sm"
                              type="button"
                              onClick={() => runManagedVisibilityAction({
                                managedResumeId: item.id,
                                action: hideHhManagedResumeFromAll,
                                successMessage: 'Готово: резюме скрыто от всех на HH.',
                              })}
                              disabled={hhTargetBusy || hhVisibilityBusyById[item.id] || item.current_visibility_mode === 'hidden_from_all'}
                            >
                              {hhVisibilityBusyById[item.id] ? 'Применяем...' : item.current_visibility_mode === 'hidden_from_all' ? 'Уже скрыто' : 'Скрыть от всех'}
                            </button>
                            <button
                              className="button button--ghost button--sm"
                              type="button"
                              onClick={() => runManagedVisibilityAction({
                                managedResumeId: item.id,
                                action: getHhManagedResumeVisibility,
                                successMessage: 'Локальный visibility-статус обновлён.',
                              })}
                              disabled={hhTargetBusy || hhVisibilityBusyById[item.id]}
                            >
                              {hhVisibilityBusyById[item.id] ? 'Обновляем...' : 'Обновить статус'}
                            </button>
                          </div>
                        )}
                      </td>
                      <td>{item.hh_resume_url ? <a href={item.hh_resume_url} target="_blank" rel="noreferrer">HH</a> : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
        </article>
      </Section>

      <Section title="Интеграция HH (MVP)" defaultOpen>
        <p className="muted-text">
          Импорт выполняется только по явному действию пользователя. Импортируются: основные поля профиля, опыт, навыки,
          языки и ссылки.
        </p>
        <p>{hhStatus.connected ? 'Статус: HH подключён' : 'Статус: HH не подключён'}</p>
        {hhStatus.last_imported_at ? <p>Последний импорт: {new Date(hhStatus.last_imported_at).toLocaleString()}</p> : null}
        <div className="recommendations-toolbar">
          <button className="button" type="button" onClick={connectHh} disabled={hhBusy}>
            {hhBusy ? 'Подключение...' : 'Подключить HH'}
          </button>
          <button className="button" type="button" onClick={importFromHh} disabled={hhBusy || !hhStatus.connected}>
            {hhBusy ? 'Импорт...' : 'Импортировать профиль из HH'}
          </button>
          <button className="button button--ghost" type="button" onClick={disconnectFromHh} disabled={hhBusy || !hhStatus.connected}>
            Disconnect HH
          </button>
        </div>
        {hhResumes.length ? (
          <SelectField
            label="Резюме HH"
            value={hhResumeId}
            onChange={(e) => setHhResumeId(e.target.value)}
            options={hhResumes.map((item) => ({ value: item.id, label: item.title }))}
          />
        ) : null}
        <hr />
        <p className="muted-text">
          Fallback/dev path: импорт из локального HH-like JSON (файл или вставка текста) без live OAuth callback.
        </p>
        <div className="settings-grid settings-grid--two">
          <label className="field">
            <span>Загрузить JSON в формате HH</span>
            <input type="file" accept=".json,application/json" onChange={onHhJsonFileUpload} />
          </label>
        </div>
        <TextAreaField
          label="JSON payload в формате HH"
          rows={8}
          value={hhJsonRaw}
          onChange={(e) => {
            setHhJsonRaw(e.target.value);
            setHhJsonError('');
            setHhJsonImportSummary(null);
          }}
          placeholder='{"me": {...}, "resumes_mine": {"items": [...]}}'
        />
        {hhJsonParseResult.error ? <ErrorBanner message={hhJsonParseResult.error} /> : null}
        {!hhJsonParseResult.error && hhJsonRaw.trim() ? (
          <div className="muted-text">
            <p>Предпросмотр:</p>
            <ul>
              <li>{hhJsonPreview.meFound ? '✓ me найден' : '✗ me не найден'}</li>
              <li>{hhJsonPreview.resumesMineFound ? '✓ resumes_mine.items найден' : '✗ resumes_mine.items не найден'}</li>
              <li>Найдено резюме: {hhJsonPreview.resumes.length}</li>
              <li>Будет импортировано: {selectedHhJsonResume?.title ?? '—'} ({selectedHhJsonResume?.id ?? '—'})</li>
            </ul>
          </div>
        ) : null}
        {hhJsonPreview.resumes.length > 1 ? (
          <SelectField
            label="Резюме из JSON"
            value={resolvedHhJsonResumeId}
            onChange={(e) => setHhJsonResumeId(e.target.value)}
            options={hhJsonPreview.resumes.map((item) => ({ value: item.id, label: `${item.title} (${item.id})` }))}
          />
        ) : null}
        <label className="field">
          <input
            type="checkbox"
            checked={hhJsonConsent}
            onChange={(e) => setHhJsonConsent(e.target.checked)}
          />
          <span>Подтверждаю импорт профиля из локального JSON в текущий профиль.</span>
        </label>
        <div className="recommendations-toolbar">
          <button
            className="button"
            type="button"
            onClick={importFromHhJson}
            disabled={hhJsonBusy || !hhJsonConsent || !hhJsonRaw.trim() || Boolean(hhJsonParseResult.error)}
          >
            {hhJsonBusy ? 'Импорт JSON...' : 'Импортировать профиль из локального JSON'}
          </button>
        </div>
        {hhJsonError ? <ErrorBanner message={hhJsonError} /> : null}
        {hhJsonImportSummary ? (
          <div className="muted-text">
            <p>Сводка импорта JSON:</p>
            <ul>
              <li>resume_id: {hhJsonImportSummary.resume_id ?? '—'}</li>
              <li>обновлённые поля: {(hhJsonImportSummary.updated_fields ?? []).join(', ') || '—'}</li>
              <li>заменённые секции: {(hhJsonImportSummary.replaced_sections ?? []).join(', ') || '—'}</li>
              <li>
                imported_at:{' '}
                {hhJsonImportSummary.imported_at ? new Date(hhJsonImportSummary.imported_at).toLocaleString() : '—'}
              </li>
            </ul>
          </div>
        ) : null}
      </Section>

      <Section title="Импорт резюме из файла" defaultOpen>
        <p className="muted-text">
          Шаги: загрузите файл резюме, получите preview распознанного черновика и примените его к текущему профилю.
        </p>
        <div className="settings-grid settings-grid--two">
          <label className="field">
            <span>Файл резюме</span>
            <input type="file" accept=".txt,.md,.docx,.pdf,.rtf,text/plain,text/markdown,application/pdf,application/rtf" onChange={onResumeImportFileChange} />
          </label>
        </div>
        <p className="muted-text">
          Поддерживаемые форматы: txt / md / docx / pdf (text-based) / rtf.
        </p>
        {resumeImportFile ? <p className="muted-text">Выбран файл: {resumeImportFile.name}</p> : null}
        <div className="recommendations-toolbar">
          <button className="button" type="button" onClick={extractAndParseResumeFile} disabled={resumeImportBusy || !resumeImportFile}>
            {resumeImportBusy ? 'Извлечение и парсинг...' : 'Извлечь и распарсить'}
          </button>
        </div>

        {resumeImportParseError ? <ErrorBanner message={resumeImportParseError} /> : null}

        {resumeImportDraftResponse ? (
          <div className="muted-text">
            <p>Предпросмотр импортируемого черновика:</p>
            <ul>
              <li>full_name: {resumeImportDraftResponse.draft?.full_name || '—'}</li>
              <li>title: {resumeImportDraftResponse.draft?.title || '—'}</li>
              <li>location: {resumeImportDraftResponse.draft?.location || '—'}</li>
              <li>summary/about: {resumeImportDraftResponse.draft?.summary_about || '—'}</li>
              <li>количество опытов: {resumeImportDraftResponse.draft?.experiences?.length ?? 0}</li>
              <li>количество навыков: {resumeImportDraftResponse.draft?.skills?.length ?? 0}</li>
              <li>количество языков: {resumeImportDraftResponse.draft?.languages?.length ?? 0}</li>
              <li>количество ссылок: {resumeImportDraftResponse.draft?.links?.length ?? 0}</li>
              <li>длина текста: {resumeImportExtractedTextLength}</li>
              <li>usable draft: {resumeImportDraftResponse.applyability?.has_useful_content ? 'да' : 'нет'}</li>
            </ul>
            {[...(resumeImportExtractionWarnings ?? []), ...(resumeImportDraftResponse.warnings ?? [])].length ? (
              <>
                <p>Предупреждения:</p>
                <ul>
                  {[...(resumeImportExtractionWarnings ?? []), ...(resumeImportDraftResponse.warnings ?? [])]
                    .map((warning, index) => (
                      <li key={`${warning}-${index}`}>{warning}</li>
                    ))}
                </ul>
              </>
            ) : (
              <p>Предупреждения: нет.</p>
            )}
          </div>
        ) : null}

        <div className="recommendations-toolbar">
          <button
            className="button"
            type="button"
            onClick={applyResumeImportToProfile}
            disabled={resumeImportBusy || !resumeImportDraftResponse?.applyability?.has_useful_content}
          >
            {resumeImportBusy ? 'Импорт в профиль...' : 'Импортировать в профиль'}
          </button>
        </div>
        {resumeImportApplyError ? <ErrorBanner message={resumeImportApplyError} /> : null}
        {resumeImportApplySummary ? (
          <div className="muted-text">
            <p>Итог импорта:</p>
            <ul>
              <li>импортированный файл: {resumeImportApplySummary.imported_file_name || '—'}</li>
              <li>обновлённые секции/поля: {(resumeImportApplySummary.updated_fields ?? []).join(', ') || '—'}</li>
              <li>заменённые секции: {(resumeImportApplySummary.replaced_sections ?? []).join(', ') || '—'}</li>
              <li>применено в: {resumeImportApplySummary.applied_at ? new Date(resumeImportApplySummary.applied_at).toLocaleString() : '—'}</li>
            </ul>
            {(resumeImportApplySummary.warnings ?? []).length ? (
              <>
                <p>Предупреждения после применения:</p>
                <ul>
                  {(resumeImportApplySummary.warnings ?? []).map((warning, index) => (
                    <li key={`${warning}-${index}`}>{warning}</li>
                  ))}
                </ul>
              </>
            ) : null}
          </div>
        ) : null}
      </Section>

      <Section title="Profile basics" defaultOpen>
        <div className="settings-grid settings-grid--two">
          <TextField label="Полное имя" value={profile.full_name ?? ''} onChange={(e) => updateProfileField('full_name', e.target.value)} />
          <TextField label="Заголовок / позиция" value={profile.title ?? ''} onChange={(e) => updateProfileField('title', e.target.value)} />
        </div>
        <TextAreaField label="О себе" value={profile.summary_about ?? ''} onChange={(e) => updateProfileField('summary_about', e.target.value)} />
      </Section>

      <Section title="Preferences & profile settings" defaultOpen>
        <div className="settings-grid settings-grid--two">
          <TextField label="Почта" value={profile.email ?? ''} onChange={(e) => updateProfileField('email', e.target.value)} />
          <TextField label="Телефон" value={profile.phone ?? ''} onChange={(e) => updateProfileField('phone', e.target.value)} />
          <TextField label="Telegram" value={profile.telegram ?? ''} onChange={(e) => updateProfileField('telegram', e.target.value)} />
          <TextField label="Страна" value={profile.country ?? ''} onChange={(e) => updateProfileField('country', e.target.value)} />
          <TextField label="Город" value={profile.city ?? ''} onChange={(e) => updateProfileField('city', e.target.value)} />
          <TextField label="Метро" value={profile.metro ?? ''} onChange={(e) => updateProfileField('metro', e.target.value)} />
          <SelectField label="Предпочитаемая занятость" value={profile.preferred_employment ?? ''} options={EMPLOYMENT_OPTIONS} onChange={(e) => updateProfileField('preferred_employment', e.target.value)} />
          <SelectField label="Предпочитаемый график" value={profile.preferred_schedule ?? ''} options={SCHEDULE_OPTIONS} onChange={(e) => updateProfileField('preferred_schedule', e.target.value)} />
          <TextField type="number" label="Срок выхода (дней)" value={profile.notice_period_days ?? ''} onChange={(e) => updateProfileField('notice_period_days', Number(e.target.value || 0))} />
          <DateField label="Готов(а) с" value={profile.available_from ?? ''} onChange={(e) => updateProfileField('available_from', e.target.value)} />
          <TextField type="number" label="Минимальная зарплата" value={profile.salary_min ?? ''} onChange={(e) => updateProfileField('salary_min', Number(e.target.value || 0))} />
          <TextField label="Гражданство" value={profile.citizenship ?? ''} onChange={(e) => updateProfileField('citizenship', e.target.value)} />
          <TextField label="Страна разрешения на работу" value={profile.work_authorization_country ?? ''} onChange={(e) => updateProfileField('work_authorization_country', e.target.value)} />
        </div>
        <div className="settings-grid settings-grid--two">
          <SwitchField label="Удалёнка возможна" checked={profile.remote_ok} onChange={(e) => updateProfileField('remote_ok', e.target.checked)} />
          <SwitchField label="Готов(а) к релокации" checked={profile.relocation_ok} onChange={(e) => updateProfileField('relocation_ok', e.target.checked)} />
          <SwitchField label="Нужна виза/спонсорство" checked={profile.needs_sponsorship} onChange={(e) => updateProfileField('needs_sponsorship', e.target.checked)} />
        </div>

        <TagInput label="Предпочитаемые индустрии" value={profile.preferred_industries ?? []} onChange={(value) => updateProfileField('preferred_industries', value)} />
        <TagInput label="Предпочитаемые типы компаний" value={profile.preferred_company_types ?? []} onChange={(value) => updateProfileField('preferred_company_types', value)} />
        <TagInput label="Теги интересов" value={profile.interest_tags ?? []} onChange={(value) => updateProfileField('interest_tags', value)} />
        <TagInput label="Предпочитаемые технологии" value={profile.preferred_tech ?? []} onChange={(value) => updateProfileField('preferred_tech', value)} />
        <TagInput label="Исключённые технологии" value={profile.excluded_tech ?? []} onChange={(value) => updateProfileField('excluded_tech', value)} />

        <TextAreaField
          label="team_preferences_json"
          rows={6}
          value={teamPreferencesText}
          onChange={(e) => setTeamPreferencesText(e.target.value)}
        />
        {teamPreferencesError ? <ErrorBanner message={teamPreferencesError} /> : null}

        <button className="button" type="button" onClick={saveProfile} disabled={profileSaving || Boolean(teamPreferencesError)}>
          {profileSaving ? 'Сохранение...' : 'Сохранить профиль'}
        </button>
      </Section>

      <Section title="Structured profile entities" defaultOpen>
        <p className="muted-text">Редактируйте структуру профиля по блокам: навыки, опыт, проекты, образование и ссылки.</p>
      </Section>

      {renderCards('Навыки', 'skills', skills, setSkills, {
        create: (payload) => createSkill(profileId, payload),
        update: (id, payload) => updateSkill(profileId, id, payload),
        remove: (id) => deleteSkill(profileId, id),
      }, (item) => `${item.name_raw || 'Новый навык'} (${item.level || '—'})`, (draft, setDraft) => (
        <div className="settings-grid settings-grid--two">
          <TextField label="Название" value={draft.name_raw ?? ''} onChange={(e) => setDraft({ ...draft, name_raw: e.target.value })} />
          <TextField label="Категория" value={draft.category ?? ''} onChange={(e) => setDraft({ ...draft, category: e.target.value })} />
          <TextField label="Уровень" value={draft.level ?? ''} onChange={(e) => setDraft({ ...draft, level: e.target.value })} />
          <TextField label="Лет опыта" type="number" value={draft.years ?? ''} onChange={(e) => setDraft({ ...draft, years: Number(e.target.value || 0) })} />
          <TextField label="Последний год использования" type="number" value={draft.last_used_year ?? ''} onChange={(e) => setDraft({ ...draft, last_used_year: Number(e.target.value || 0) })} />
          <SwitchField label="Ключевой" checked={draft.is_primary} onChange={(e) => setDraft({ ...draft, is_primary: e.target.checked })} />
          <TextAreaField label="Подтверждение" value={draft.evidence_text ?? ''} onChange={(e) => setDraft({ ...draft, evidence_text: e.target.value })} />
        </div>
      ), savingByKey, saveItem, removeItem)}

      {renderCards('Опыт', 'experiences', experiences, setExperiences, {
        create: (payload) => createExperience(profileId, payload),
        update: (id, payload) => updateExperience(profileId, id, payload),
        remove: (id) => deleteExperience(profileId, id),
      }, (item) => `${item.company_name || 'Новый опыт'} — ${item.position_title || '—'}`, (draft, setDraft) => (
        <div className="settings-grid settings-grid--two">
          <TextField label="Компания" value={draft.company_name ?? ''} onChange={(e) => setDraft({ ...draft, company_name: e.target.value })} />
          <TextField label="Должность" value={draft.position_title ?? ''} onChange={(e) => setDraft({ ...draft, position_title: e.target.value })} />
          <TextField label="Локация" value={draft.location ?? ''} onChange={(e) => setDraft({ ...draft, location: e.target.value })} />
          <DateField label="Дата начала" value={draft.start_date ?? ''} onChange={(e) => setDraft({ ...draft, start_date: e.target.value })} />
          <DateField label="Дата окончания" value={draft.end_date ?? ''} onChange={(e) => setDraft({ ...draft, end_date: e.target.value })} />
          <SwitchField label="Текущее место" checked={draft.is_current} onChange={(e) => setDraft({ ...draft, is_current: e.target.checked })} />
          <TextAreaField label="Обязанности" value={draft.responsibilities_text ?? ''} onChange={(e) => setDraft({ ...draft, responsibilities_text: e.target.value })} />
          <TextAreaField label="Достижения" value={draft.achievements_text ?? ''} onChange={(e) => setDraft({ ...draft, achievements_text: e.target.value })} />
          <TextAreaField label="Стек технологий" value={draft.tech_stack_text ?? ''} onChange={(e) => setDraft({ ...draft, tech_stack_text: e.target.value })} />
        </div>
      ), savingByKey, saveItem, removeItem)}

      {renderCards('Проекты', 'projects', projects, setProjects, {
        create: (payload) => createProject(profileId, payload), update: (id, payload) => updateProject(profileId, id, payload), remove: (id) => deleteProject(profileId, id),
      }, (item) => item.name || 'Новый проект', (draft, setDraft) => (
        <div className="settings-grid settings-grid--two">
          <TextField label="Название" value={draft.name ?? ''} onChange={(e) => setDraft({ ...draft, name: e.target.value })} />
          <TextField label="Роль" value={draft.role ?? ''} onChange={(e) => setDraft({ ...draft, role: e.target.value })} />
          <DateField label="Дата начала" value={draft.start_date ?? ''} onChange={(e) => setDraft({ ...draft, start_date: e.target.value })} />
          <DateField label="Дата окончания" value={draft.end_date ?? ''} onChange={(e) => setDraft({ ...draft, end_date: e.target.value })} />
          <TextAreaField label="Описание" value={draft.description_text ?? ''} onChange={(e) => setDraft({ ...draft, description_text: e.target.value })} />
          <TextAreaField label="Стек технологий" value={draft.tech_stack_text ?? ''} onChange={(e) => setDraft({ ...draft, tech_stack_text: e.target.value })} />
          <TextField label="Ссылка" value={draft.url ?? ''} onChange={(e) => setDraft({ ...draft, url: e.target.value })} />
        </div>
      ), savingByKey, saveItem, removeItem)}

      {renderCards('Достижения', 'achievements', achievements, setAchievements, {
        create: (payload) => createAchievement(profileId, payload), update: (id, payload) => updateAchievement(profileId, id, payload), remove: (id) => deleteAchievement(profileId, id),
      }, (item) => item.title || 'Новое достижение', (draft, setDraft) => (
        <div className="settings-grid settings-grid--two">
          <TextField label="Название" value={draft.title ?? ''} onChange={(e) => setDraft({ ...draft, title: e.target.value })} />
          <TextField label="Метрика" value={draft.metric ?? ''} onChange={(e) => setDraft({ ...draft, metric: e.target.value })} />
          <DateField label="Дата достижения" value={draft.achieved_at ?? ''} onChange={(e) => setDraft({ ...draft, achieved_at: e.target.value })} />
          <SelectField label="Связанный опыт" options={experienceOptions} value={String(draft.related_experience_id ?? '')} onChange={(e) => setDraft({ ...draft, related_experience_id: Number(e.target.value || 0) || null })} />
          <SelectField label="Связанный проект" options={projectOptions} value={String(draft.related_project_id ?? '')} onChange={(e) => setDraft({ ...draft, related_project_id: Number(e.target.value || 0) || null })} />
          <TextAreaField label="Описание" value={draft.description_text ?? ''} onChange={(e) => setDraft({ ...draft, description_text: e.target.value })} />
        </div>
      ), savingByKey, saveItem, removeItem)}

      {renderCards('Образование', 'education', education, setEducation, {
        create: (payload) => createEducation(profileId, payload), update: (id, payload) => updateEducation(profileId, id, payload), remove: (id) => deleteEducation(profileId, id),
      }, (item) => item.institution || 'Новое образование', (draft, setDraft) => (
        <div className="settings-grid settings-grid--two">
          <TextField label="Учебное заведение" value={draft.institution ?? ''} onChange={(e) => setDraft({ ...draft, institution: e.target.value })} />
          <TextField label="Степень" value={draft.degree_level ?? ''} onChange={(e) => setDraft({ ...draft, degree_level: e.target.value })} />
          <TextField label="Специальность" value={draft.field_of_study ?? ''} onChange={(e) => setDraft({ ...draft, field_of_study: e.target.value })} />
          <TextField type="number" label="Год начала" value={draft.start_year ?? ''} onChange={(e) => setDraft({ ...draft, start_year: Number(e.target.value || 0) })} />
          <TextField type="number" label="Год окончания" value={draft.end_year ?? ''} onChange={(e) => setDraft({ ...draft, end_year: Number(e.target.value || 0) })} />
          <TextField type="number" label="GPA" value={draft.gpa ?? ''} onChange={(e) => setDraft({ ...draft, gpa: Number(e.target.value || 0) })} />
          <TextAreaField label="Описание" value={draft.description_text ?? ''} onChange={(e) => setDraft({ ...draft, description_text: e.target.value })} />
        </div>
      ), savingByKey, saveItem, removeItem)}

      {renderCards('Сертификаты', 'certificates', certificates, setCertificates, {
        create: (payload) => createCertificate(profileId, payload), update: (id, payload) => updateCertificate(profileId, id, payload), remove: (id) => deleteCertificate(profileId, id),
      }, (item) => item.name || 'Новый сертификат', (draft, setDraft) => (
        <div className="settings-grid settings-grid--two">
          <TextField label="Название" value={draft.name ?? ''} onChange={(e) => setDraft({ ...draft, name: e.target.value })} />
          <TextField label="Выдавшая организация" value={draft.issuer ?? ''} onChange={(e) => setDraft({ ...draft, issuer: e.target.value })} />
          <DateField label="Дата выдачи" value={draft.issued_at ?? ''} onChange={(e) => setDraft({ ...draft, issued_at: e.target.value })} />
          <DateField label="Срок действия" value={draft.expires_at ?? ''} onChange={(e) => setDraft({ ...draft, expires_at: e.target.value })} />
          <TextField label="Ссылка" value={draft.url ?? ''} onChange={(e) => setDraft({ ...draft, url: e.target.value })} />
        </div>
      ), savingByKey, saveItem, removeItem)}

      {renderCards('Языки', 'languages', languages, setLanguages, {
        create: (payload) => createLanguage(profileId, payload), update: (id, payload) => updateLanguage(profileId, id, payload), remove: (id) => deleteLanguage(profileId, id),
      }, (item) => `${item.language || 'Язык'} (${item.level || '—'})`, (draft, setDraft) => (
        <div className="settings-grid settings-grid--two">
          <TextField label="Язык" value={draft.language ?? ''} onChange={(e) => setDraft({ ...draft, language: e.target.value })} />
          <TextField label="Уровень" value={draft.level ?? ''} onChange={(e) => setDraft({ ...draft, level: e.target.value })} />
        </div>
      ), savingByKey, saveItem, removeItem)}

      {renderCards('Ссылки', 'links', links, setLinks, {
        create: (payload) => createLink(profileId, payload), update: (id, payload) => updateLink(profileId, id, payload), remove: (id) => deleteLink(profileId, id),
      }, (item) => item.label || item.url || 'Новая ссылка', (draft, setDraft) => (
        <div className="settings-grid settings-grid--two">
          <TextField label="Тип" value={draft.type ?? ''} onChange={(e) => setDraft({ ...draft, type: e.target.value })} />
          <TextField label="Ссылка" value={draft.url ?? ''} onChange={(e) => setDraft({ ...draft, url: e.target.value })} />
          <TextField label="Подпись" value={draft.label ?? ''} onChange={(e) => setDraft({ ...draft, label: e.target.value })} />
        </div>
      ), savingByKey, saveItem, removeItem)}

      <Section title="Документы" defaultOpen>
        <p className="muted-text">Рабочий модуль версий резюме и cover letters: черновики, согласование и быстрые правки.</p>
        <SwitchField label="Только approved резюме" checked={approvedOnlyResume} onChange={(e) => setApprovedOnlyResume(e.target.checked)} />
        {renderDocCards('resumes', visibleResumes, setResumes, {
          create: (payload) => createResumeVersion(profileId, payload),
          update: (id, payload) => updateResumeVersion(profileId, id, payload),
          remove: (id) => deleteResumeVersion(profileId, id),
        }, savingByKey, saveItem, removeItem, approveDoc)}

        <SwitchField label="Только approved cover letters" checked={approvedOnlyLetter} onChange={(e) => setApprovedOnlyLetter(e.target.checked)} />
        {renderDocCards('letters', visibleLetters, setLetters, {
          create: (payload) => createCoverLetterVersion(profileId, payload),
          update: (id, payload) => updateCoverLetterVersion(profileId, id, payload),
          remove: (id) => deleteCoverLetterVersion(profileId, id),
        }, savingByKey, saveItem, removeItem, approveDoc)}
      </Section>
    </section>
  );
}

function renderCards(title, sectionKey, items, setItems, ops, summaryFormatter, renderFields, savingByKey, saveItem, removeItem) {
  return (
    <Section title={title} defaultOpen>
      <button type="button" className="button button--ghost" onClick={() => setItems((current) => [{ ...emptyBySection[sectionKey] }, ...current])}>
        Добавить
      </button>
      <div className="editor-list">
        {items.map((item, index) => {
          const localId = item.id ?? `new-${index}`;
          const key = `${sectionKey}-${localId}`;
          return (
            <InlineEditorCard
              key={key}
              title={`${title} #${item.id ?? 'new'}`}
              summary={summaryFormatter(item)}
              value={item}
              disabled={Boolean(savingByKey[key])}
              onSave={(draft) => saveItem(sectionKey, draft, { ...ops, setItems })}
              onDelete={(id) => removeItem(sectionKey, id, { ...ops, setItems })}
              renderFields={renderFields}
            />
          );
        })}
      </div>
    </Section>
  );
}

function renderDocCards(sectionKey, items, setItems, ops, savingByKey, saveItem, removeItem, approveDoc) {
  return (
    <div className="editor-list">
      <button type="button" className="button button--ghost" onClick={() => setItems((current) => [{ ...emptyBySection[sectionKey] }, ...current])}>
        Create
      </button>
      {items.map((item, index) => {
        const localId = item.id ?? `new-${index}`;
        const key = `${sectionKey}-${localId}`;
        const statusMeta = DOCUMENT_STATUS_META[item.status] || { label: item.status || 'Draft', tone: 'draft' };
        return (
          <InlineEditorCard
            key={key}
            title={`${item.title || 'Без названия'}`}
            summary={`Статус: ${statusMeta.label} · created_at: ${item.created_at || '—'} · vacancy_id: ${item.vacancy_id || '—'}`}
            value={item}
            disabled={Boolean(savingByKey[key])}
            onSave={(draft) => saveItem(sectionKey, draft, { ...ops, setItems })}
            onDelete={(id) => removeItem(sectionKey, id, { ...ops, setItems })}
            renderFields={(draft, setDraft) => (
              <div className="document-editor">
                <div className="inline-status-row">
                  <span className={`doc-state-badge doc-state-badge--${statusMeta.tone}`}>{statusMeta.label}</span>
                  <span className="muted-text">source: {draft.source || 'user'}</span>
                </div>
                <div className="settings-grid settings-grid--two">
                  <TextField label="Название" value={draft.title ?? ''} onChange={(e) => setDraft({ ...draft, title: e.target.value })} />
                  {'subject' in draft ? <TextField label="Тема" value={draft.subject ?? ''} onChange={(e) => setDraft({ ...draft, subject: e.target.value })} /> : null}
                  <TextField label="ID вакансии" type="number" value={draft.vacancy_id ?? ''} onChange={(e) => setDraft({ ...draft, vacancy_id: Number(e.target.value || 0) || null })} />
                </div>
                <TextAreaField label="Содержимое" rows={8} value={draft.content_text ?? ''} onChange={(e) => setDraft({ ...draft, content_text: e.target.value })} />
                {draft.id ? (
                  <button type="button" className="button button--ghost" onClick={() => approveDoc(sectionKey, draft.id)}>
                    Approve version
                  </button>
                ) : null}
              </div>
            )}
          />
        );
      })}
    </div>
  );
}
