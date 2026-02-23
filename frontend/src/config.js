export const API_PREFIX = '/api/v1';
export const DEFAULT_PROFILE_ID = 1;
export const DEFAULT_LIMIT = 50;

export function getApiBaseUrl() {
  const baseUrl = import.meta.env.VITE_API_BASE_URL;

  if (!baseUrl) {
    return '';
  }

  return baseUrl.replace(/\/+$/, '');
}
