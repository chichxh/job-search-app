import { API_PREFIX, getApiBaseUrl } from '../config.js';

export async function apiFetch(path, options) {
  const baseUrl = getApiBaseUrl();
  const response = await fetch(`${baseUrl}${API_PREFIX}${path}`, options);
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
