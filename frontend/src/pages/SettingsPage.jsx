import { useEffect, useMemo, useState } from 'react';

import {
  getProfile,
  getTask,
  recomputeRecommendations,
  updateProfile,
} from '../api/endpoints.js';
import { DEFAULT_PROFILE_ID } from '../config.js';
import ErrorBanner from '../components/ErrorBanner.jsx';
import Loading from '../components/Loading.jsx';
import {
  DEFAULT_JOBSEARCH_SETTINGS,
  loadJobSearchSettings,
  saveJobSearchSettings,
} from '../utils/settings.js';

export default function SettingsPage() {
  const [profileForm, setProfileForm] = useState({
    title: '',
    skills_text: '',
    resume_text: '',
  });
  const [loading, setLoading] = useState(true);
  const [profileError, setProfileError] = useState('');
  const [saveError, setSaveError] = useState('');
  const [successMessage, setSuccessMessage] = useState('');
  const [savingProfile, setSavingProfile] = useState(false);

  const [settings, setSettings] = useState(DEFAULT_JOBSEARCH_SETTINGS);
  const [settingsMessage, setSettingsMessage] = useState('');

  const [taskId, setTaskId] = useState('');
  const [taskState, setTaskState] = useState('IDLE');
  const [taskError, setTaskError] = useState('');

  useEffect(() => {
    setSettings(loadJobSearchSettings());
  }, []);

  useEffect(() => {
    async function fetchProfile() {
      setLoading(true);
      setProfileError('');

      try {
        const profile = await getProfile(DEFAULT_PROFILE_ID);
        setProfileForm({
          title: profile.title ?? '',
          skills_text: profile.skills_text ?? '',
          resume_text: profile.resume_text ?? '',
        });
      } catch (requestError) {
        setProfileError(requestError.message || 'Не удалось загрузить профиль.');
      } finally {
        setLoading(false);
      }
    }

    fetchProfile();
  }, []);

  useEffect(() => {
    if (!taskId) {
      return undefined;
    }

    let isActive = true;
    const intervalId = setInterval(pollTaskStatus, 2000);

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
        }

        if (task.state === 'FAILURE') {
          setTaskError(task.error || 'Не удалось пересчитать рекомендации.');
          setTaskId('');
        }
      } catch (requestError) {
        if (!isActive) {
          return;
        }

        setTaskError(requestError.message || 'Не удалось обновить статус задачи.');
        setTaskState('FAILURE');
        setTaskId('');
      }
    }

    pollTaskStatus();

    return () => {
      isActive = false;
      clearInterval(intervalId);
    };
  }, [taskId]);

  const isRecomputeRunning = useMemo(() => Boolean(taskId), [taskId]);

  function handleProfileChange(event) {
    const { name, value } = event.target;
    setProfileForm((currentForm) => ({
      ...currentForm,
      [name]: value,
    }));
  }

  function handleSettingsChange(event) {
    const { name, type, checked, value } = event.target;

    setSettings((currentSettings) => ({
      ...currentSettings,
      [name]: type === 'checkbox' ? checked : value,
    }));
  }

  async function handleSaveProfile(event) {
    event.preventDefault();
    setSavingProfile(true);
    setSaveError('');
    setSuccessMessage('');
    setTaskError('');

    try {
      await updateProfile(DEFAULT_PROFILE_ID, profileForm);
      setSuccessMessage('Профиль сохранён.');

      if (settings.autoRecomputeAfterProfileSave) {
        const response = await recomputeRecommendations(
          DEFAULT_PROFILE_ID,
          settings.recommendationsLimit,
        );
        setTaskId(response.task_id);
        setTaskState('PENDING');
      }
    } catch (requestError) {
      setSaveError(requestError.message || 'Не удалось сохранить профиль.');
    } finally {
      setSavingProfile(false);
    }
  }

  function handleSaveSettings(event) {
    event.preventDefault();
    const persisted = saveJobSearchSettings(settings);
    setSettings(persisted);
    setSettingsMessage('Настройки рекомендаций сохранены.');
  }

  return (
    <section className="page-stack">
      <h1>Настройки</h1>

      <section className="settings-section">
        <h2 className="settings-section__title">Профиль (profile_id=1)</h2>

        {loading ? <Loading message="Загрузка профиля..." /> : null}
        {!loading && profileError ? <ErrorBanner message={profileError} /> : null}

        {!loading && !profileError ? (
          <form className="settings-form" onSubmit={handleSaveProfile}>
            <label className="settings-form__field">
              <span>Title</span>
              <input
                type="text"
                name="title"
                value={profileForm.title}
                onChange={handleProfileChange}
              />
            </label>

            <label className="settings-form__field">
              <span>Skills text</span>
              <textarea
                name="skills_text"
                rows={5}
                value={profileForm.skills_text}
                onChange={handleProfileChange}
              />
            </label>

            <label className="settings-form__field">
              <span>Resume text</span>
              <textarea
                name="resume_text"
                rows={7}
                value={profileForm.resume_text}
                onChange={handleProfileChange}
              />
            </label>

            <button className="recommendations-toolbar__button" type="submit" disabled={savingProfile}>
              {savingProfile ? 'Сохранение...' : 'Сохранить'}
            </button>
          </form>
        ) : null}

        {saveError ? <ErrorBanner message={saveError} /> : null}
        {successMessage ? <p className="success-banner">{successMessage}</p> : null}

        {isRecomputeRunning ? (
          <p className="loading">Задача {taskId}: {taskState}</p>
        ) : taskState === 'SUCCESS' ? (
          <p className="loading">Рекомендации пересчитаны.</p>
        ) : null}

        {taskError ? <ErrorBanner message={taskError} /> : null}
      </section>

      <section className="settings-section">
        <h2 className="settings-section__title">Настройки рекомендаций</h2>

        <form className="settings-form" onSubmit={handleSaveSettings}>
          <label className="settings-form__field">
            <span>Recommendations limit (10..200)</span>
            <input
              type="number"
              min={10}
              max={200}
              name="recommendationsLimit"
              value={settings.recommendationsLimit}
              onChange={handleSettingsChange}
            />
          </label>

          <label className="vacancy-filters__toggle">
            <input
              type="checkbox"
              name="hideReject"
              checked={settings.hideReject}
              onChange={handleSettingsChange}
            />
            <span>Скрывать reject в рекомендациях</span>
          </label>

          <label className="vacancy-filters__toggle">
            <input
              type="checkbox"
              name="autoRecomputeAfterProfileSave"
              checked={settings.autoRecomputeAfterProfileSave}
              onChange={handleSettingsChange}
            />
            <span>Автопересчёт рекомендаций после сохранения профиля</span>
          </label>

          <label className="settings-form__field">
            <span>Scoring mode</span>
            <select name="scoringMode" value={settings.scoringMode} onChange={handleSettingsChange}>
              <option value="Balanced">Balanced</option>
              <option value="Conservative">Conservative</option>
              <option value="Startup">Startup</option>
              <option value="Enterprise">Enterprise</option>
            </select>
          </label>

          <button className="recommendations-toolbar__button" type="submit">
            Сохранить настройки
          </button>

          {settingsMessage ? <p className="success-banner">{settingsMessage}</p> : null}
        </form>
      </section>
    </section>
  );
}
