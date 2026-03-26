import { API_PREFIX, getApiBaseUrl } from '../config.js';
import { getAccessToken } from '../utils/auth.js';

export async function apiFetch(path, options = {}) {
  const baseUrl = getApiBaseUrl();
  const headers = new Headers(options.headers ?? {});
  const token = getAccessToken();

  if (token && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  const response = await fetch(`${baseUrl}${API_PREFIX}${path}`, {
    ...options,
    headers,
  });
  const contentType = response.headers.get('content-type') ?? '';

  if (!response.ok) {
    let errorPayload;

    if (contentType.includes('application/json')) {
      errorPayload = await response.json().catch(() => null);
    } else {
      errorPayload = await response.text().catch(() => '');
    }

    const details =
      typeof errorPayload === 'string'
        ? errorPayload
        : errorPayload?.detail ?? JSON.stringify(errorPayload ?? {});

    throw new Error(`API request failed (${response.status} ${response.statusText})${details ? `: ${details}` : ''}`);
  }

  if (!contentType.includes('application/json')) {
    return null;
  }

  return response.json();
}
