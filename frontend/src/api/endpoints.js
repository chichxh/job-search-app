import { DEFAULT_LIMIT } from '../config.js';
import { getCurrentProfileId } from '../utils/auth.js';
import { apiFetch } from './client.js';

function resolveProfileId(profileId) {
  const resolved = profileId ?? getCurrentProfileId();

  if (!Number.isInteger(resolved) || resolved <= 0) {
    throw new Error('Current profile is not available. Please log in again.');
  }

  return resolved;
}

export function registerUser(payload) {
  return apiFetch('/auth/register', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export function loginUser(payload) {
  return apiFetch('/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export function getCurrentUser(accessToken) {
  const headers = accessToken ? { Authorization: `Bearer ${accessToken}` } : undefined;
  return apiFetch('/auth/me', { headers });
}

export const getVacancies = () => apiFetch('/vacancies');
export const getVacancyById = (vacancyId) => apiFetch(`/vacancies/${vacancyId}`);

export const getProfile = (profileId) => apiFetch(`/profiles/${resolveProfileId(profileId)}`);

export const updateProfile = (profileId, payload) =>
  apiFetch(`/profiles/${resolveProfileId(profileId)}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

const listProfileResource = (profileId, resource) => apiFetch(`/profiles/${resolveProfileId(profileId)}/${resource}`);
const createProfileResource = (profileId, resource, payload) =>
  apiFetch(`/profiles/${resolveProfileId(profileId)}/${resource}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
const updateProfileResource = (profileId, resource, id, payload) =>
  apiFetch(`/profiles/${resolveProfileId(profileId)}/${resource}/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
const deleteProfileResource = (profileId, resource, id) =>
  apiFetch(`/profiles/${resolveProfileId(profileId)}/${resource}/${id}`, { method: 'DELETE' });

export const listExperiences = (profileId) => listProfileResource(profileId, 'experiences');
export const createExperience = (profileId, payload) => createProfileResource(profileId, 'experiences', payload);
export const updateExperience = (profileId, id, payload) => updateProfileResource(profileId, 'experiences', id, payload);
export const deleteExperience = (profileId, id) => deleteProfileResource(profileId, 'experiences', id);

export const listProjects = (profileId) => listProfileResource(profileId, 'projects');
export const createProject = (profileId, payload) => createProfileResource(profileId, 'projects', payload);
export const updateProject = (profileId, id, payload) => updateProfileResource(profileId, 'projects', id, payload);
export const deleteProject = (profileId, id) => deleteProfileResource(profileId, 'projects', id);

export const listAchievements = (profileId) => listProfileResource(profileId, 'achievements');
export const createAchievement = (profileId, payload) => createProfileResource(profileId, 'achievements', payload);
export const updateAchievement = (profileId, id, payload) => updateProfileResource(profileId, 'achievements', id, payload);
export const deleteAchievement = (profileId, id) => deleteProfileResource(profileId, 'achievements', id);

export const listEducation = (profileId) => listProfileResource(profileId, 'education');
export const createEducation = (profileId, payload) => createProfileResource(profileId, 'education', payload);
export const updateEducation = (profileId, id, payload) => updateProfileResource(profileId, 'education', id, payload);
export const deleteEducation = (profileId, id) => deleteProfileResource(profileId, 'education', id);

export const listCertificates = (profileId) => listProfileResource(profileId, 'certificates');
export const createCertificate = (profileId, payload) => createProfileResource(profileId, 'certificates', payload);
export const updateCertificate = (profileId, id, payload) => updateProfileResource(profileId, 'certificates', id, payload);
export const deleteCertificate = (profileId, id) => deleteProfileResource(profileId, 'certificates', id);

export const listSkills = (profileId) => listProfileResource(profileId, 'skills');
export const createSkill = (profileId, payload) => createProfileResource(profileId, 'skills', payload);
export const updateSkill = (profileId, id, payload) => updateProfileResource(profileId, 'skills', id, payload);
export const deleteSkill = (profileId, id) => deleteProfileResource(profileId, 'skills', id);

export const listLanguages = (profileId) => listProfileResource(profileId, 'languages');
export const createLanguage = (profileId, payload) => createProfileResource(profileId, 'languages', payload);
export const updateLanguage = (profileId, id, payload) => updateProfileResource(profileId, 'languages', id, payload);
export const deleteLanguage = (profileId, id) => deleteProfileResource(profileId, 'languages', id);

export const listLinks = (profileId) => listProfileResource(profileId, 'links');
export const createLink = (profileId, payload) => createProfileResource(profileId, 'links', payload);
export const updateLink = (profileId, id, payload) => updateProfileResource(profileId, 'links', id, payload);
export const deleteLink = (profileId, id) => deleteProfileResource(profileId, 'links', id);

export const listResumeVersions = (profileId) => listProfileResource(profileId, 'resume-versions');
export const createResumeVersion = (profileId, payload) => createProfileResource(profileId, 'resume-versions', payload);
export const updateResumeVersion = (profileId, id, payload) => updateProfileResource(profileId, 'resume-versions', id, payload);
export const approveResumeVersion = (profileId, id) =>
  apiFetch(`/profiles/${resolveProfileId(profileId)}/resume-versions/${id}/approve`, { method: 'POST' });
export const deleteResumeVersion = (profileId, id) => deleteProfileResource(profileId, 'resume-versions', id);

export const listCoverLetterVersions = (profileId) => listProfileResource(profileId, 'cover-letter-versions');
export const createCoverLetterVersion = (profileId, payload) => createProfileResource(profileId, 'cover-letter-versions', payload);
export const updateCoverLetterVersion = (profileId, id, payload) => updateProfileResource(profileId, 'cover-letter-versions', id, payload);
export const approveCoverLetterVersion = (profileId, id) =>
  apiFetch(`/profiles/${resolveProfileId(profileId)}/cover-letter-versions/${id}/approve`, { method: 'POST' });
export const deleteCoverLetterVersion = (profileId, id) => deleteProfileResource(profileId, 'cover-letter-versions', id);

export const listApplications = (profileId) => listProfileResource(profileId, 'applications');
export const createApplication = (profileId, payload) => createProfileResource(profileId, 'applications', payload);
export const getApplication = (profileId, applicationId) =>
  apiFetch(`/profiles/${resolveProfileId(profileId)}/applications/${applicationId}`);
export const updateApplication = (profileId, applicationId, payload) =>
  apiFetch(`/profiles/${resolveProfileId(profileId)}/applications/${applicationId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
export const changeApplicationStatus = (profileId, applicationId, payload) =>
  apiFetch(`/profiles/${resolveProfileId(profileId)}/applications/${applicationId}/status`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
export const listApplicationHistory = (profileId, applicationId) =>
  apiFetch(`/profiles/${resolveProfileId(profileId)}/applications/${applicationId}/history`);
export const deleteApplication = (profileId, applicationId) =>
  apiFetch(`/profiles/${resolveProfileId(profileId)}/applications/${applicationId}`, { method: 'DELETE' });

export const getRecommendations = (profileId, limit = DEFAULT_LIMIT) =>
  apiFetch(`/profiles/${resolveProfileId(profileId)}/recommendations?limit=${limit}`);

export const recomputeRecommendations = (profileId, limit = DEFAULT_LIMIT) =>
  apiFetch(`/profiles/${resolveProfileId(profileId)}/recommendations/recompute?limit=${limit}`, { method: 'POST' });

export const recomputeAllProfileData = (profileId, limit = DEFAULT_LIMIT) =>
  apiFetch(`/dev/profiles/${resolveProfileId(profileId)}/recompute-all?limit=${limit}`, { method: 'POST' });

export const getTask = (taskId) => apiFetch(`/tasks/${taskId}`);

export const startHhImport = (payload) =>
  apiFetch('/import/hh', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

export const getHhConnectionStatus = () => apiFetch('/integrations/hh/status');
export const startHhOAuthConnect = () => apiFetch('/integrations/hh/connect/start', { method: 'POST' });
export const listHhResumes = () => apiFetch('/integrations/hh/resumes');
export const importProfileFromHh = (payload) =>
  apiFetch('/integrations/hh/import', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
export const importProfileFromHhJson = (payload) =>
  apiFetch('/integrations/hh/import-json', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
export const disconnectHh = () => apiFetch('/integrations/hh/connection', { method: 'DELETE' });


export const getHhBrowserConnectionStatus = () => apiFetch('/integrations/hh-browser/status');
export const getHhBrowserConnectState = () => apiFetch('/integrations/hh-browser/connect/state');
export const startHhBrowserConnection = (payload = {}) =>
  apiFetch('/integrations/hh-browser/connect/start', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
export const submitHhBrowserIdentifier = (payload) =>
  apiFetch('/integrations/hh-browser/connect/identifier', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
export const submitHhBrowserPassword = (payload) =>
  apiFetch('/integrations/hh-browser/connect/password', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
export const submitHhBrowserCode = (payload) =>
  apiFetch('/integrations/hh-browser/connect/code', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
export const cancelHhBrowserConnection = () => apiFetch('/integrations/hh-browser/connect/cancel', { method: 'POST' });
export const disconnectHhBrowserConnection = () => apiFetch('/integrations/hh-browser/disconnect', { method: 'POST' });
export const checkHhBrowserSession = () => apiFetch('/integrations/hh-browser/session/check', { method: 'POST' });
export const restoreHhBrowserSession = () => apiFetch('/integrations/hh-browser/session/restore', { method: 'POST' });

export const extractResumeImportFile = (profileId, file) => {
  const formData = new FormData();
  formData.append('file', file);

  return apiFetch(`/profiles/${resolveProfileId(profileId)}/resume-import/extract`, {
    method: 'POST',
    body: formData,
  });
};

export const parseResumeImportText = (profileId, extractedText) =>
  apiFetch(`/profiles/${resolveProfileId(profileId)}/resume-import/parse`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ extracted_text: extractedText }),
  });

export const applyResumeImportDraft = (profileId, payload) =>
  apiFetch(`/profiles/${resolveProfileId(profileId)}/resume-import/apply`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

export const getTailoring = (profileId, vacancyId) =>
  apiFetch(`/profiles/${resolveProfileId(profileId)}/vacancies/${vacancyId}/tailoring`);

export const generateResumeDraft = (profileId, vacancyId) =>
  apiFetch(`/profiles/${resolveProfileId(profileId)}/vacancies/${vacancyId}/resume/generate`, { method: 'POST' });

export const generateCoverLetterDraft = (profileId, vacancyId) =>
  apiFetch(`/profiles/${resolveProfileId(profileId)}/vacancies/${vacancyId}/cover-letter/generate`, { method: 'POST' });
