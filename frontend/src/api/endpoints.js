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

export function getRecommendations(profileId = DEFAULT_PROFILE_ID, limit = DEFAULT_LIMIT) {
  return apiFetch(`/profiles/${profileId}/recommendations?limit=${limit}`);
}

export function recomputeRecommendations(profileId = DEFAULT_PROFILE_ID, limit = DEFAULT_LIMIT) {
  return apiFetch(`/profiles/${profileId}/recommendations/recompute?limit=${limit}`, {
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
