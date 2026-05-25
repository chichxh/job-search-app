import { useEffect, useMemo, useState } from 'react';

import {
  applyResumeImportDraft,
  extractResumeImportFile,
  getHhConnectionStatus,
  getProfile,
  demoConnectHh,
  parseResumeImportText,
} from '../api/endpoints.js';
import { useAuth } from '../auth/useAuth.js';
import ErrorBanner from '../components/ErrorBanner.jsx';
import Loading from '../components/Loading.jsx';
import PageHeader from '../components/ui/PageHeader.jsx';
import SectionCard from '../components/ui/SectionCard.jsx';
import StatusPill from '../components/ui/StatusPill.jsx';

const SUPPORTED_FILE_EXTENSIONS = ['txt', 'pdf', 'docx'];

function normalizeResumeImportError(error) {
  const rawMessage = (error?.message || '').trim();
  const message = rawMessage.toLowerCase();

  if (!rawMessage) return 'Не удалось обработать резюме. Попробуйте снова.';
  if (message.includes('too short') || message.includes('nothing useful')) return 'Текст резюме слишком короткий или не содержит полезных данных.';
  if (message.includes('unsupported') || message.includes('format')) return 'Неподдерживаемый формат файла. Загрузите .txt, .pdf или .docx.';
  if (message.includes('no extractable text') || message.includes('empty') || message.includes('cannot extract')) return 'Не удалось извлечь текст из файла. Попробуйте другой файл или вставьте текст вручную.';
  if (message.includes('failed') || message.includes('error') || message.includes('exception')) return 'Ошибка backend при обработке резюме. Попробуйте еще раз.';
  return rawMessage;
}


export default function SettingsPage() {
  const { profileId } = useAuth();
  const [loading, setLoading] = useState(true);
  const [pageError, setPageError] = useState('');

  const [hhStatus, setHhStatus] = useState({ connected: false });
  const [hhBusy, setHhBusy] = useState(false);
  const [hhError, setHhError] = useState('');
  const [hhImportedProfile, setHhImportedProfile] = useState(null);
  const [hhSuccess, setHhSuccess] = useState('');

  const [resumeText, setResumeText] = useState('');
  const [resumeFile, setResumeFile] = useState(null);
  const [resumeBusy, setResumeBusy] = useState(false);
  const [resumeError, setResumeError] = useState('');
  const [resumeDraft, setResumeDraft] = useState(null);
  const [applySuccess, setApplySuccess] = useState('');

  useEffect(() => {
    let ignore = false;

    async function bootstrap() {
      try {
        const [status, profile] = await Promise.all([
          getHhConnectionStatus(),
          getProfile(profileId),
        ]);
        if (ignore) return;
        setHhStatus(status ?? { connected: false });
        setHhImportedProfile(profile ?? null);
      } catch (error) {
        if (!ignore) {
          setPageError('Не удалось загрузить настройки. Обновите страницу и попробуйте снова.');
        }
      } finally {
        if (!ignore) setLoading(false);
      }
    }

    bootstrap();
    return () => {
      ignore = true;
    };
  }, [profileId]);

  const hhUiStatus = useMemo(() => {
    if (hhBusy) return { label: 'Подключение...', tone: 'info' };
    if (hhStatus?.connected) return { label: 'Подключено', tone: 'success' };
    return { label: 'Не подключено', tone: 'neutral' };
  }, [hhBusy, hhStatus?.connected]);

  const hhSummary = useMemo(() => {
    if (!hhImportedProfile) return null;
    const fullName = [hhImportedProfile.first_name, hhImportedProfile.last_name].filter(Boolean).join(' ') || hhImportedProfile.full_name || '—';
    const skillsCount = Array.isArray(hhImportedProfile.skills) ? hhImportedProfile.skills.length : 0;
    const experienceCount = Array.isArray(hhImportedProfile.experiences) ? hhImportedProfile.experiences.length : 0;

    return {
      fullName,
      headline: hhImportedProfile.professional_title || hhImportedProfile.current_position || '—',
      city: hhImportedProfile.location_city || hhImportedProfile.location || '—',
      skillsCount,
      experienceCount,
    };
  }, [hhImportedProfile]);

  async function handleHhAuth() {
    setHhBusy(true);
    setHhError('');
    setHhSuccess('');
    try {
      const response = await demoConnectHh();
      const importedProfile = response?.profile ?? response?.data?.profile ?? null;
      setHhStatus({ connected: true });
      setHhImportedProfile(importedProfile);
      setHhSuccess('Данные профиля импортированы из HeadHunter в демонстрационном режиме');
    } catch (error) {
      const message = error?.message || '';
      if (message.toLowerCase().includes('demo_mode') || message.toLowerCase().includes('demo mode')) {
        setHhError('Демо-авторизация HH отключена. Включите DEMO_MODE=true');
      } else {
        setHhError('Не удалось выполнить авторизацию через HH. Попробуйте еще раз позже.');
      }
    } finally {
      setHhBusy(false);
    }
  }

  async function handleBuildProfile() {
    setResumeBusy(true);
    setResumeError('');
    setApplySuccess('');
    setResumeDraft(null);

    try {
      const hasText = Boolean(resumeText.trim());
      const hasFile = Boolean(resumeFile);

      if (hasText && hasFile) {
        throw new Error('Выберите только один способ: текст или файл');
      }

      if (!hasText && !hasFile) {
        throw new Error('Добавьте текст резюме или загрузите файл');
      }

      let textPayload = resumeText.trim();
      if (resumeFile) {
        const extension = resumeFile.name.includes('.') ? resumeFile.name.split('.').pop().toLowerCase() : '';
        if (!SUPPORTED_FILE_EXTENSIONS.includes(extension)) {
          throw new Error('Поддерживаются только файлы txt, pdf и docx.');
        }
        const extractResult = await extractResumeImportFile(profileId, resumeFile);
        textPayload = extractResult?.extracted_text?.trim() ?? '';
      }

      if (!textPayload) {
        throw new Error('Не удалось извлечь текст из файла. Попробуйте другой файл или вставьте текст вручную.');
      }

      const parseResult = await parseResumeImportText(profileId, textPayload);
      setResumeDraft(parseResult?.draft ?? null);
    } catch (error) {
      setResumeError(normalizeResumeImportError(error));
    } finally {
      setResumeBusy(false);
    }
  }

  async function handleApplyProfile() {
    if (!resumeDraft) return;
    setResumeBusy(true);
    setResumeError('');
    setApplySuccess('');

    try {
      await applyResumeImportDraft(profileId, {
        draft: resumeDraft,
        update_main_fields: true,
        replace_sections: ['experiences', 'skills', 'education'],
      });
      setApplySuccess('Профиль обновлен');
      const profile = await getProfile(profileId);
      setHhImportedProfile(profile ?? null);
    } catch (error) {
      setResumeError(normalizeResumeImportError(error));
    } finally {
      setResumeBusy(false);
    }
  }

  if (loading) return <Loading label="Загружаем настройки" />;

  return (

    <div className="settings-demo-page">
      <PageHeader
        eyebrow="Настройки"
        title="Профиль для поиска вакансий"
        subtitle="Подключите HeadHunter или загрузите резюме, чтобы быстро заполнить профиль для демонстрации."
      />

      {pageError ? <ErrorBanner message={pageError} /> : null}


      <div className="settings-demo-grid">
        <SectionCard
          title="Авторизация HeadHunter"
          subtitle="Подключите аккаунт HeadHunter, чтобы импортировать данные профиля и использовать их для подбора вакансий."
        >
          <p className="settings-demo-hint">Доступно в демонстрационном режиме</p>

          <div className="settings-demo-status-row">
            <span>Статус подключения</span>
            <StatusPill tone={hhUiStatus.tone}>{hhUiStatus.label}</StatusPill>
          </div>

          {hhError ? <ErrorBanner message={hhError} /> : null}

          {hhSuccess ? <p className="settings-demo-success">{hhSuccess}</p> : null}

          <div className="settings-demo-actions">
            <button type="button" className="button button-primary" onClick={handleHhAuth} disabled={hhBusy}>
              {hhBusy ? 'Подключаем...' : 'Авторизоваться через HH'}
            </button>
          </div>

          {hhSummary ? (
            <div className="settings-demo-preview">
              <h4>Импортированные данные</h4>
              <ul>
                <li><strong>Имя:</strong> {hhSummary.fullName}</li>
                <li><strong>Профессиональный заголовок:</strong> {hhSummary.headline}</li>
                <li><strong>Город:</strong> {hhSummary.city}</li>
                <li><strong>Количество навыков:</strong> {hhSummary.skillsCount}</li>
                <li><strong>Количество записей опыта:</strong> {hhSummary.experienceCount}</li>
              </ul>
            </div>
          ) : null}
        </SectionCard>

        <SectionCard
          title="Нет резюме в HH?"
          subtitle="Вставьте текст резюме или загрузите файл, система сформирует профиль соискателя."
        >
          {resumeError ? <ErrorBanner message={resumeError} /> : null}
          {applySuccess ? <p className="settings-demo-success">{applySuccess}</p> : null}

          <label className="settings-demo-field">
            <span>Вставьте текст резюме</span>
            <textarea rows={8} value={resumeText} onChange={(event) => setResumeText(event.target.value)} placeholder="Вставьте резюме в свободной форме" />
          </label>

          <label className="settings-demo-field">
            <span>Загрузить файл резюме (.txt, .pdf, .docx)</span>
            <input type="file" accept=".txt,.pdf,.docx" onChange={(event) => setResumeFile(event.target.files?.[0] ?? null)} />
          </label>

          <div className="settings-demo-actions">
            <button type="button" className="button button-primary" onClick={handleBuildProfile} disabled={resumeBusy}>
              Сформировать профиль
            </button>
          </div>

          {resumeDraft ? (
            <div className="settings-demo-preview">
              <h4>Распознанные данные</h4>
              <ul>
                <li><strong>ФИО:</strong> {resumeDraft.full_name || '—'}</li>
                <li><strong>Должность:</strong> {resumeDraft.title || '—'}</li>
                <li><strong>Навыки:</strong> {Array.isArray(resumeDraft.skills) ? resumeDraft.skills.map((item) => item.name_raw || item.name).filter(Boolean).join(', ') || '—' : '—'}</li>
                <li><strong>Опыт:</strong> {Array.isArray(resumeDraft.experiences) ? `${resumeDraft.experiences.length} записей` : '—'}</li>
                <li><strong>Образование:</strong> {Array.isArray(resumeDraft.education) && resumeDraft.education.length ? `${resumeDraft.education.length} записей` : 'не распознано'}</li>
                <li><strong>Краткое summary:</strong> {resumeDraft.summary_about || '—'}</li>
              </ul>

              <button type="button" className="button button-secondary" onClick={handleApplyProfile} disabled={resumeBusy}>
                Применить к профилю
              </button>
            </div>
          ) : null}
        </SectionCard>
      </div>
    </div>
  );
}
