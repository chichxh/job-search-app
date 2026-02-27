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
  getProfile,
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
import { DEFAULT_LIMIT, DEFAULT_PROFILE_ID } from '../config.js';

const EMPLOYMENT_OPTIONS = [
  { value: 'full_time', label: 'Full-time' },
  { value: 'part_time', label: 'Part-time' },
  { value: 'contract', label: 'Contract' },
  { value: 'internship', label: 'Internship' },
  { value: 'project', label: 'Project' },
  { value: 'volunteer', label: 'Volunteer' },
];

const SCHEDULE_OPTIONS = [
  { value: 'full_day', label: 'Full day' },
  { value: 'shift', label: 'Shift' },
  { value: 'flexible', label: 'Flexible' },
  { value: 'remote', label: 'Remote' },
  { value: 'hybrid', label: 'Hybrid' },
];

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
        ] = await Promise.all([
          getProfile(DEFAULT_PROFILE_ID),
          listExperiences(DEFAULT_PROFILE_ID),
          listProjects(DEFAULT_PROFILE_ID),
          listAchievements(DEFAULT_PROFILE_ID),
          listEducation(DEFAULT_PROFILE_ID),
          listCertificates(DEFAULT_PROFILE_ID),
          listSkills(DEFAULT_PROFILE_ID),
          listLanguages(DEFAULT_PROFILE_ID),
          listLinks(DEFAULT_PROFILE_ID),
          listResumeVersions(DEFAULT_PROFILE_ID),
          listCoverLetterVersions(DEFAULT_PROFILE_ID),
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
      } catch (requestError) {
        setError(requestError.message || 'Ошибка загрузки настроек.');
      } finally {
        setLoading(false);
      }
    }

    loadData();
  }, []);

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
      const updated = await updateProfile(DEFAULT_PROFILE_ID, payload);
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
      const result = await updater(DEFAULT_PROFILE_ID, id);
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
      await recomputeAllProfileData(DEFAULT_PROFILE_ID, DEFAULT_LIMIT);
      setToast('Пересчёт всего запущен.');
    } catch {
      setError('Endpoint /dev/profiles/1/recompute-all недоступен.');
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

  const visibleResumes = approvedOnlyResume ? resumes.filter((item) => item.status === 'approved') : resumes;
  const visibleLetters = approvedOnlyLetter ? letters.filter((item) => item.status === 'approved') : letters;

  if (loading) {
    return <Loading message="Загрузка /settings..." />;
  }

  return (
    <section className="page-stack">
      <h1>Settings (profile_id=1)</h1>
      {error ? <ErrorBanner message={error} /> : null}
      {toast ? <p className="success-banner">{toast}</p> : null}

      <div className="recommendations-toolbar">
        <button className="button" type="button" onClick={() => recomputeRecommendations(DEFAULT_PROFILE_ID, DEFAULT_LIMIT)}>
          Пересчитать рекомендации
        </button>
        <button className="button button--ghost" type="button" onClick={runRecomputeAll}>
          Пересчитать всё
        </button>
        <Link to="/recommendations" className="button button--ghost">Перейти к рекомендациям</Link>
      </div>

      <div className="settings-grid settings-grid--two">
        <TextField label="Full name" value={profile.full_name ?? ''} onChange={(e) => updateProfileField('full_name', e.target.value)} />
        <TextField label="Headline / title" value={profile.title ?? ''} onChange={(e) => updateProfileField('title', e.target.value)} />
      </div>
      <TextAreaField label="Summary about" value={profile.summary_about ?? ''} onChange={(e) => updateProfileField('summary_about', e.target.value)} />

      <Section title="A-G. Поля таблицы profiles" defaultOpen>
        <div className="settings-grid settings-grid--two">
          <TextField label="Email" value={profile.email ?? ''} onChange={(e) => updateProfileField('email', e.target.value)} />
          <TextField label="Phone" value={profile.phone ?? ''} onChange={(e) => updateProfileField('phone', e.target.value)} />
          <TextField label="Telegram" value={profile.telegram ?? ''} onChange={(e) => updateProfileField('telegram', e.target.value)} />
          <TextField label="Country" value={profile.country ?? ''} onChange={(e) => updateProfileField('country', e.target.value)} />
          <TextField label="City" value={profile.city ?? ''} onChange={(e) => updateProfileField('city', e.target.value)} />
          <TextField label="Metro" value={profile.metro ?? ''} onChange={(e) => updateProfileField('metro', e.target.value)} />
          <SelectField label="Preferred employment" value={profile.preferred_employment ?? ''} options={EMPLOYMENT_OPTIONS} onChange={(e) => updateProfileField('preferred_employment', e.target.value)} />
          <SelectField label="Preferred schedule" value={profile.preferred_schedule ?? ''} options={SCHEDULE_OPTIONS} onChange={(e) => updateProfileField('preferred_schedule', e.target.value)} />
          <TextField type="number" label="Notice period (days)" value={profile.notice_period_days ?? ''} onChange={(e) => updateProfileField('notice_period_days', Number(e.target.value || 0))} />
          <DateField label="Available from" value={profile.available_from ?? ''} onChange={(e) => updateProfileField('available_from', e.target.value)} />
          <TextField type="number" label="Salary min" value={profile.salary_min ?? ''} onChange={(e) => updateProfileField('salary_min', Number(e.target.value || 0))} />
          <TextField label="Citizenship" value={profile.citizenship ?? ''} onChange={(e) => updateProfileField('citizenship', e.target.value)} />
          <TextField label="Work authorization country" value={profile.work_authorization_country ?? ''} onChange={(e) => updateProfileField('work_authorization_country', e.target.value)} />
        </div>
        <div className="settings-grid settings-grid--two">
          <SwitchField label="Remote OK" checked={profile.remote_ok} onChange={(e) => updateProfileField('remote_ok', e.target.checked)} />
          <SwitchField label="Relocation OK" checked={profile.relocation_ok} onChange={(e) => updateProfileField('relocation_ok', e.target.checked)} />
          <SwitchField label="Needs sponsorship" checked={profile.needs_sponsorship} onChange={(e) => updateProfileField('needs_sponsorship', e.target.checked)} />
        </div>

        <TagInput label="Preferred industries" value={profile.preferred_industries ?? []} onChange={(value) => updateProfileField('preferred_industries', value)} />
        <TagInput label="Preferred company types" value={profile.preferred_company_types ?? []} onChange={(value) => updateProfileField('preferred_company_types', value)} />
        <TagInput label="Interest tags" value={profile.interest_tags ?? []} onChange={(value) => updateProfileField('interest_tags', value)} />
        <TagInput label="Preferred tech" value={profile.preferred_tech ?? []} onChange={(value) => updateProfileField('preferred_tech', value)} />
        <TagInput label="Excluded tech" value={profile.excluded_tech ?? []} onChange={(value) => updateProfileField('excluded_tech', value)} />

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

      {renderCards('Навыки', 'skills', skills, setSkills, {
        create: (payload) => createSkill(DEFAULT_PROFILE_ID, payload),
        update: (id, payload) => updateSkill(DEFAULT_PROFILE_ID, id, payload),
        remove: (id) => deleteSkill(DEFAULT_PROFILE_ID, id),
      }, (item) => `${item.name_raw || 'Новый навык'} (${item.level || '—'})`, (draft, setDraft) => (
        <div className="settings-grid settings-grid--two">
          <TextField label="Name" value={draft.name_raw ?? ''} onChange={(e) => setDraft({ ...draft, name_raw: e.target.value })} />
          <TextField label="Category" value={draft.category ?? ''} onChange={(e) => setDraft({ ...draft, category: e.target.value })} />
          <TextField label="Level" value={draft.level ?? ''} onChange={(e) => setDraft({ ...draft, level: e.target.value })} />
          <TextField label="Years" type="number" value={draft.years ?? ''} onChange={(e) => setDraft({ ...draft, years: Number(e.target.value || 0) })} />
          <TextField label="Last used year" type="number" value={draft.last_used_year ?? ''} onChange={(e) => setDraft({ ...draft, last_used_year: Number(e.target.value || 0) })} />
          <SwitchField label="Primary" checked={draft.is_primary} onChange={(e) => setDraft({ ...draft, is_primary: e.target.checked })} />
          <TextAreaField label="Evidence" value={draft.evidence_text ?? ''} onChange={(e) => setDraft({ ...draft, evidence_text: e.target.value })} />
        </div>
      ), savingByKey, saveItem, removeItem)}

      {renderCards('Опыт', 'experiences', experiences, setExperiences, {
        create: (payload) => createExperience(DEFAULT_PROFILE_ID, payload),
        update: (id, payload) => updateExperience(DEFAULT_PROFILE_ID, id, payload),
        remove: (id) => deleteExperience(DEFAULT_PROFILE_ID, id),
      }, (item) => `${item.company_name || 'Новый опыт'} — ${item.position_title || '—'}`, (draft, setDraft) => (
        <div className="settings-grid settings-grid--two">
          <TextField label="Company" value={draft.company_name ?? ''} onChange={(e) => setDraft({ ...draft, company_name: e.target.value })} />
          <TextField label="Position" value={draft.position_title ?? ''} onChange={(e) => setDraft({ ...draft, position_title: e.target.value })} />
          <TextField label="Location" value={draft.location ?? ''} onChange={(e) => setDraft({ ...draft, location: e.target.value })} />
          <DateField label="Start date" value={draft.start_date ?? ''} onChange={(e) => setDraft({ ...draft, start_date: e.target.value })} />
          <DateField label="End date" value={draft.end_date ?? ''} onChange={(e) => setDraft({ ...draft, end_date: e.target.value })} />
          <SwitchField label="Current" checked={draft.is_current} onChange={(e) => setDraft({ ...draft, is_current: e.target.checked })} />
          <TextAreaField label="Responsibilities" value={draft.responsibilities_text ?? ''} onChange={(e) => setDraft({ ...draft, responsibilities_text: e.target.value })} />
          <TextAreaField label="Achievements" value={draft.achievements_text ?? ''} onChange={(e) => setDraft({ ...draft, achievements_text: e.target.value })} />
          <TextAreaField label="Tech stack" value={draft.tech_stack_text ?? ''} onChange={(e) => setDraft({ ...draft, tech_stack_text: e.target.value })} />
        </div>
      ), savingByKey, saveItem, removeItem)}

      {renderCards('Проекты', 'projects', projects, setProjects, {
        create: (payload) => createProject(DEFAULT_PROFILE_ID, payload), update: (id, payload) => updateProject(DEFAULT_PROFILE_ID, id, payload), remove: (id) => deleteProject(DEFAULT_PROFILE_ID, id),
      }, (item) => item.name || 'Новый проект', (draft, setDraft) => (
        <div className="settings-grid settings-grid--two">
          <TextField label="Name" value={draft.name ?? ''} onChange={(e) => setDraft({ ...draft, name: e.target.value })} />
          <TextField label="Role" value={draft.role ?? ''} onChange={(e) => setDraft({ ...draft, role: e.target.value })} />
          <DateField label="Start date" value={draft.start_date ?? ''} onChange={(e) => setDraft({ ...draft, start_date: e.target.value })} />
          <DateField label="End date" value={draft.end_date ?? ''} onChange={(e) => setDraft({ ...draft, end_date: e.target.value })} />
          <TextAreaField label="Description" value={draft.description_text ?? ''} onChange={(e) => setDraft({ ...draft, description_text: e.target.value })} />
          <TextAreaField label="Tech stack" value={draft.tech_stack_text ?? ''} onChange={(e) => setDraft({ ...draft, tech_stack_text: e.target.value })} />
          <TextField label="URL" value={draft.url ?? ''} onChange={(e) => setDraft({ ...draft, url: e.target.value })} />
        </div>
      ), savingByKey, saveItem, removeItem)}

      {renderCards('Достижения', 'achievements', achievements, setAchievements, {
        create: (payload) => createAchievement(DEFAULT_PROFILE_ID, payload), update: (id, payload) => updateAchievement(DEFAULT_PROFILE_ID, id, payload), remove: (id) => deleteAchievement(DEFAULT_PROFILE_ID, id),
      }, (item) => item.title || 'Новое достижение', (draft, setDraft) => (
        <div className="settings-grid settings-grid--two">
          <TextField label="Title" value={draft.title ?? ''} onChange={(e) => setDraft({ ...draft, title: e.target.value })} />
          <TextField label="Metric" value={draft.metric ?? ''} onChange={(e) => setDraft({ ...draft, metric: e.target.value })} />
          <DateField label="Achieved at" value={draft.achieved_at ?? ''} onChange={(e) => setDraft({ ...draft, achieved_at: e.target.value })} />
          <SelectField label="Related experience" options={experienceOptions} value={String(draft.related_experience_id ?? '')} onChange={(e) => setDraft({ ...draft, related_experience_id: Number(e.target.value || 0) || null })} />
          <SelectField label="Related project" options={projectOptions} value={String(draft.related_project_id ?? '')} onChange={(e) => setDraft({ ...draft, related_project_id: Number(e.target.value || 0) || null })} />
          <TextAreaField label="Description" value={draft.description_text ?? ''} onChange={(e) => setDraft({ ...draft, description_text: e.target.value })} />
        </div>
      ), savingByKey, saveItem, removeItem)}

      {renderCards('Образование', 'education', education, setEducation, {
        create: (payload) => createEducation(DEFAULT_PROFILE_ID, payload), update: (id, payload) => updateEducation(DEFAULT_PROFILE_ID, id, payload), remove: (id) => deleteEducation(DEFAULT_PROFILE_ID, id),
      }, (item) => item.institution || 'Новое образование', (draft, setDraft) => (
        <div className="settings-grid settings-grid--two">
          <TextField label="Institution" value={draft.institution ?? ''} onChange={(e) => setDraft({ ...draft, institution: e.target.value })} />
          <TextField label="Degree" value={draft.degree_level ?? ''} onChange={(e) => setDraft({ ...draft, degree_level: e.target.value })} />
          <TextField label="Field of study" value={draft.field_of_study ?? ''} onChange={(e) => setDraft({ ...draft, field_of_study: e.target.value })} />
          <TextField type="number" label="Start year" value={draft.start_year ?? ''} onChange={(e) => setDraft({ ...draft, start_year: Number(e.target.value || 0) })} />
          <TextField type="number" label="End year" value={draft.end_year ?? ''} onChange={(e) => setDraft({ ...draft, end_year: Number(e.target.value || 0) })} />
          <TextField type="number" label="GPA" value={draft.gpa ?? ''} onChange={(e) => setDraft({ ...draft, gpa: Number(e.target.value || 0) })} />
          <TextAreaField label="Description" value={draft.description_text ?? ''} onChange={(e) => setDraft({ ...draft, description_text: e.target.value })} />
        </div>
      ), savingByKey, saveItem, removeItem)}

      {renderCards('Сертификаты', 'certificates', certificates, setCertificates, {
        create: (payload) => createCertificate(DEFAULT_PROFILE_ID, payload), update: (id, payload) => updateCertificate(DEFAULT_PROFILE_ID, id, payload), remove: (id) => deleteCertificate(DEFAULT_PROFILE_ID, id),
      }, (item) => item.name || 'Новый сертификат', (draft, setDraft) => (
        <div className="settings-grid settings-grid--two">
          <TextField label="Name" value={draft.name ?? ''} onChange={(e) => setDraft({ ...draft, name: e.target.value })} />
          <TextField label="Issuer" value={draft.issuer ?? ''} onChange={(e) => setDraft({ ...draft, issuer: e.target.value })} />
          <DateField label="Issued at" value={draft.issued_at ?? ''} onChange={(e) => setDraft({ ...draft, issued_at: e.target.value })} />
          <DateField label="Expires at" value={draft.expires_at ?? ''} onChange={(e) => setDraft({ ...draft, expires_at: e.target.value })} />
          <TextField label="URL" value={draft.url ?? ''} onChange={(e) => setDraft({ ...draft, url: e.target.value })} />
        </div>
      ), savingByKey, saveItem, removeItem)}

      {renderCards('Языки', 'languages', languages, setLanguages, {
        create: (payload) => createLanguage(DEFAULT_PROFILE_ID, payload), update: (id, payload) => updateLanguage(DEFAULT_PROFILE_ID, id, payload), remove: (id) => deleteLanguage(DEFAULT_PROFILE_ID, id),
      }, (item) => `${item.language || 'Язык'} (${item.level || '—'})`, (draft, setDraft) => (
        <div className="settings-grid settings-grid--two">
          <TextField label="Language" value={draft.language ?? ''} onChange={(e) => setDraft({ ...draft, language: e.target.value })} />
          <TextField label="Level" value={draft.level ?? ''} onChange={(e) => setDraft({ ...draft, level: e.target.value })} />
        </div>
      ), savingByKey, saveItem, removeItem)}

      {renderCards('Ссылки', 'links', links, setLinks, {
        create: (payload) => createLink(DEFAULT_PROFILE_ID, payload), update: (id, payload) => updateLink(DEFAULT_PROFILE_ID, id, payload), remove: (id) => deleteLink(DEFAULT_PROFILE_ID, id),
      }, (item) => item.label || item.url || 'Новая ссылка', (draft, setDraft) => (
        <div className="settings-grid settings-grid--two">
          <TextField label="Type" value={draft.type ?? ''} onChange={(e) => setDraft({ ...draft, type: e.target.value })} />
          <TextField label="URL" value={draft.url ?? ''} onChange={(e) => setDraft({ ...draft, url: e.target.value })} />
          <TextField label="Label" value={draft.label ?? ''} onChange={(e) => setDraft({ ...draft, label: e.target.value })} />
        </div>
      ), savingByKey, saveItem, removeItem)}

      <Section title="Документы" defaultOpen>
        <SwitchField label="Только approved резюме" checked={approvedOnlyResume} onChange={(e) => setApprovedOnlyResume(e.target.checked)} />
        {renderDocCards('resumes', visibleResumes, setResumes, {
          create: (payload) => createResumeVersion(DEFAULT_PROFILE_ID, payload),
          update: (id, payload) => updateResumeVersion(DEFAULT_PROFILE_ID, id, payload),
          remove: (id) => deleteResumeVersion(DEFAULT_PROFILE_ID, id),
        }, savingByKey, saveItem, removeItem, approveDoc)}

        <SwitchField label="Только approved cover letters" checked={approvedOnlyLetter} onChange={(e) => setApprovedOnlyLetter(e.target.checked)} />
        {renderDocCards('letters', visibleLetters, setLetters, {
          create: (payload) => createCoverLetterVersion(DEFAULT_PROFILE_ID, payload),
          update: (id, payload) => updateCoverLetterVersion(DEFAULT_PROFILE_ID, id, payload),
          remove: (id) => deleteCoverLetterVersion(DEFAULT_PROFILE_ID, id),
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
        return (
          <InlineEditorCard
            key={key}
            title={`${item.title || 'Без названия'} [${item.status}]`}
            summary={`created_at: ${item.created_at || '—'}, vacancy_id: ${item.vacancy_id || '—'}`}
            value={item}
            disabled={Boolean(savingByKey[key])}
            onSave={(draft) => saveItem(sectionKey, draft, { ...ops, setItems })}
            onDelete={(id) => removeItem(sectionKey, id, { ...ops, setItems })}
            renderFields={(draft, setDraft) => (
              <div>
                <div className="settings-grid settings-grid--two">
                  <TextField label="Title" value={draft.title ?? ''} onChange={(e) => setDraft({ ...draft, title: e.target.value })} />
                  {'subject' in draft ? <TextField label="Subject" value={draft.subject ?? ''} onChange={(e) => setDraft({ ...draft, subject: e.target.value })} /> : null}
                  <TextField label="Vacancy ID" type="number" value={draft.vacancy_id ?? ''} onChange={(e) => setDraft({ ...draft, vacancy_id: Number(e.target.value || 0) || null })} />
                </div>
                <TextAreaField label="Content" rows={8} value={draft.content_text ?? ''} onChange={(e) => setDraft({ ...draft, content_text: e.target.value })} />
                {draft.id ? (
                  <button type="button" className="button button--ghost" onClick={() => approveDoc(sectionKey, draft.id)}>
                    Approve
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
