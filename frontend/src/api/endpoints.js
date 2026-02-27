import { DEFAULT_LIMIT, DEFAULT_PROFILE_ID } from '../config.js';
import { apiFetch } from './client.js';

export function getVacancies() {
  return apiFetch('/vacancies');
}

export function getVacancyById(vacancyId) {
  return apiFetch(`/vacancies/${vacancyId}`);
}

export function getProfile(profileId = DEFAULT_PROFILE_ID) {
  return apiFetch(`/profiles/${profileId}`);
}

export function updateProfile(profileId = DEFAULT_PROFILE_ID, payload) {
  return apiFetch(`/profiles/${profileId}`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });
}

function listProfileResource(profileId, resource) {
  return apiFetch(`/profiles/${profileId}/${resource}`);
}

function createProfileResource(profileId, resource, payload) {
  return apiFetch(`/profiles/${profileId}/${resource}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });
}

function updateProfileResource(profileId, resource, id, payload) {
  return apiFetch(`/profiles/${profileId}/${resource}/${id}`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });
}

function deleteProfileResource(profileId, resource, id) {
  return apiFetch(`/profiles/${profileId}/${resource}/${id}`, {
    method: 'DELETE',
  });
}

export const listExperiences = (profileId = DEFAULT_PROFILE_ID) => listProfileResource(profileId, 'experiences');
export const createExperience = (profileId = DEFAULT_PROFILE_ID, payload) =>
  createProfileResource(profileId, 'experiences', payload);
export const updateExperience = (profileId = DEFAULT_PROFILE_ID, id, payload) =>
  updateProfileResource(profileId, 'experiences', id, payload);
export const deleteExperience = (profileId = DEFAULT_PROFILE_ID, id) =>
  deleteProfileResource(profileId, 'experiences', id);

export const listProjects = (profileId = DEFAULT_PROFILE_ID) => listProfileResource(profileId, 'projects');
export const createProject = (profileId = DEFAULT_PROFILE_ID, payload) =>
  createProfileResource(profileId, 'projects', payload);
export const updateProject = (profileId = DEFAULT_PROFILE_ID, id, payload) =>
  updateProfileResource(profileId, 'projects', id, payload);
export const deleteProject = (profileId = DEFAULT_PROFILE_ID, id) => deleteProfileResource(profileId, 'projects', id);

export const listAchievements = (profileId = DEFAULT_PROFILE_ID) => listProfileResource(profileId, 'achievements');
export const createAchievement = (profileId = DEFAULT_PROFILE_ID, payload) =>
  createProfileResource(profileId, 'achievements', payload);
export const updateAchievement = (profileId = DEFAULT_PROFILE_ID, id, payload) =>
  updateProfileResource(profileId, 'achievements', id, payload);
export const deleteAchievement = (profileId = DEFAULT_PROFILE_ID, id) =>
  deleteProfileResource(profileId, 'achievements', id);

export const listEducation = (profileId = DEFAULT_PROFILE_ID) => listProfileResource(profileId, 'education');
export const createEducation = (profileId = DEFAULT_PROFILE_ID, payload) =>
  createProfileResource(profileId, 'education', payload);
export const updateEducation = (profileId = DEFAULT_PROFILE_ID, id, payload) =>
  updateProfileResource(profileId, 'education', id, payload);
export const deleteEducation = (profileId = DEFAULT_PROFILE_ID, id) => deleteProfileResource(profileId, 'education', id);

export const listCertificates = (profileId = DEFAULT_PROFILE_ID) => listProfileResource(profileId, 'certificates');
export const createCertificate = (profileId = DEFAULT_PROFILE_ID, payload) =>
  createProfileResource(profileId, 'certificates', payload);
export const updateCertificate = (profileId = DEFAULT_PROFILE_ID, id, payload) =>
  updateProfileResource(profileId, 'certificates', id, payload);
export const deleteCertificate = (profileId = DEFAULT_PROFILE_ID, id) =>
  deleteProfileResource(profileId, 'certificates', id);

export const listSkills = (profileId = DEFAULT_PROFILE_ID) => listProfileResource(profileId, 'skills');
export const createSkill = (profileId = DEFAULT_PROFILE_ID, payload) => createProfileResource(profileId, 'skills', payload);
export const updateSkill = (profileId = DEFAULT_PROFILE_ID, id, payload) =>
  updateProfileResource(profileId, 'skills', id, payload);
export const deleteSkill = (profileId = DEFAULT_PROFILE_ID, id) => deleteProfileResource(profileId, 'skills', id);

export const listLanguages = (profileId = DEFAULT_PROFILE_ID) => listProfileResource(profileId, 'languages');
export const createLanguage = (profileId = DEFAULT_PROFILE_ID, payload) =>
  createProfileResource(profileId, 'languages', payload);
export const updateLanguage = (profileId = DEFAULT_PROFILE_ID, id, payload) =>
  updateProfileResource(profileId, 'languages', id, payload);
export const deleteLanguage = (profileId = DEFAULT_PROFILE_ID, id) => deleteProfileResource(profileId, 'languages', id);

export const listLinks = (profileId = DEFAULT_PROFILE_ID) => listProfileResource(profileId, 'links');
export const createLink = (profileId = DEFAULT_PROFILE_ID, payload) => createProfileResource(profileId, 'links', payload);
export const updateLink = (profileId = DEFAULT_PROFILE_ID, id, payload) =>
  updateProfileResource(profileId, 'links', id, payload);
export const deleteLink = (profileId = DEFAULT_PROFILE_ID, id) => deleteProfileResource(profileId, 'links', id);

export const listResumeVersions = (profileId = DEFAULT_PROFILE_ID) => listProfileResource(profileId, 'resume-versions');
export const createResumeVersion = (profileId = DEFAULT_PROFILE_ID, payload) =>
  createProfileResource(profileId, 'resume-versions', payload);
export const updateResumeVersion = (profileId = DEFAULT_PROFILE_ID, id, payload) =>
  updateProfileResource(profileId, 'resume-versions', id, payload);
export const approveResumeVersion = (profileId = DEFAULT_PROFILE_ID, id) =>
  apiFetch(`/profiles/${profileId}/resume-versions/${id}/approve`, { method: 'POST' });
export const deleteResumeVersion = (profileId = DEFAULT_PROFILE_ID, id) =>
  deleteProfileResource(profileId, 'resume-versions', id);

export const listCoverLetterVersions = (profileId = DEFAULT_PROFILE_ID) =>
  listProfileResource(profileId, 'cover-letter-versions');
export const createCoverLetterVersion = (profileId = DEFAULT_PROFILE_ID, payload) =>
  createProfileResource(profileId, 'cover-letter-versions', payload);
export const updateCoverLetterVersion = (profileId = DEFAULT_PROFILE_ID, id, payload) =>
  updateProfileResource(profileId, 'cover-letter-versions', id, payload);
export const approveCoverLetterVersion = (profileId = DEFAULT_PROFILE_ID, id) =>
  apiFetch(`/profiles/${profileId}/cover-letter-versions/${id}/approve`, { method: 'POST' });
export const deleteCoverLetterVersion = (profileId = DEFAULT_PROFILE_ID, id) =>
  deleteProfileResource(profileId, 'cover-letter-versions', id);

export function getRecommendations(profileId = DEFAULT_PROFILE_ID, limit = DEFAULT_LIMIT) {
  return apiFetch(`/profiles/${profileId}/recommendations?limit=${limit}`);
}

export function recomputeRecommendations(profileId = DEFAULT_PROFILE_ID, limit = DEFAULT_LIMIT) {
  return apiFetch(`/profiles/${profileId}/recommendations/recompute?limit=${limit}`, {
    method: 'POST',
  });
}

export function recomputeAllProfileData(profileId = DEFAULT_PROFILE_ID, limit = DEFAULT_LIMIT) {
  return apiFetch(`/dev/profiles/${profileId}/recompute-all?limit=${limit}`, {
    method: 'POST',
  });
}

export function getTask(taskId) {
  return apiFetch(`/tasks/${taskId}`);
}

export function startHhImport(payload) {
  return apiFetch('/import/hh', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });
}

export function getTailoring(profileId = DEFAULT_PROFILE_ID, vacancyId) {
  return apiFetch(`/profiles/${profileId}/vacancies/${vacancyId}/tailoring`);
}
