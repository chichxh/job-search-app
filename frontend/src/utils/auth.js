export const AUTH_SESSION_KEY = 'jobsearch_auth_session';

export function normalizeAuthSession(raw) {
  if (!raw || typeof raw !== 'object') {
    return null;
  }

  const accessToken = typeof raw.accessToken === 'string' ? raw.accessToken.trim() : '';
  const profileId = Number(raw.profileId);
  const user = raw.user && typeof raw.user === 'object' ? raw.user : null;

  if (!accessToken || !Number.isInteger(profileId) || profileId <= 0) {
    return null;
  }

  return {
    accessToken,
    profileId,
    user,
  };
}

export function loadAuthSession() {
  try {
    const raw = window.localStorage.getItem(AUTH_SESSION_KEY);
    if (!raw) {
      return null;
    }

    return normalizeAuthSession(JSON.parse(raw));
  } catch {
    return null;
  }
}

export function saveAuthSession(session) {
  const normalized = normalizeAuthSession(session);

  if (!normalized) {
    window.localStorage.removeItem(AUTH_SESSION_KEY);
    return null;
  }

  window.localStorage.setItem(AUTH_SESSION_KEY, JSON.stringify(normalized));
  return normalized;
}

export function clearAuthSession() {
  window.localStorage.removeItem(AUTH_SESSION_KEY);
}

export function getAccessToken() {
  return loadAuthSession()?.accessToken ?? '';
}

export function getCurrentProfileId() {
  return loadAuthSession()?.profileId ?? null;
}
