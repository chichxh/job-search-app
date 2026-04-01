import { useCallback, useEffect, useMemo, useState } from 'react';

import { loginUser, registerUser, getCurrentUser } from '../api/endpoints.js';
import { clearAuthSession, loadAuthSession, saveAuthSession } from '../utils/auth.js';
import { AuthContext } from './context.js';

function parseError(error, fallback) {
  const raw = String(error?.message ?? '').trim();
  if (!raw) {
    return fallback;
  }

  const detailMatch = raw.match(/\):\s*(.+)$/);
  return detailMatch?.[1] ? detailMatch[1] : raw;
}

export function AuthProvider({ children }) {
  const [authSession, setAuthSession] = useState(() => loadAuthSession());
  const [isBootstrapping, setIsBootstrapping] = useState(Boolean(loadAuthSession()?.accessToken));

  const clearSession = useCallback(() => {
    clearAuthSession();
    setAuthSession(null);
  }, []);

  const applyToken = useCallback(async (accessToken) => {
    const me = await getCurrentUser(accessToken);
    const nextSession = saveAuthSession({
      accessToken,
      profileId: me.profile_id,
      user: me.user,
    });
    setAuthSession(nextSession);
    return me;
  }, []);

  useEffect(() => {
    async function bootstrap() {
      const existing = loadAuthSession();
      if (!existing?.accessToken) {
        setIsBootstrapping(false);
        return;
      }

      try {
        await applyToken(existing.accessToken);
      } catch {
        clearSession();
      } finally {
        setIsBootstrapping(false);
      }
    }

    bootstrap();
  }, [applyToken, clearSession]);

  const login = useCallback(async ({ email, password }) => {
    const response = await loginUser({ email, password });
    try {
      await applyToken(response.access_token);
    } catch (error) {
      throw new Error(parseError(error, 'Вход выполнен, но не удалось загрузить данные текущего пользователя.'));
    }
  }, [applyToken]);

  const register = useCallback(async ({ email, password }) => {
    const response = await registerUser({ email, password });
    try {
      await applyToken(response.access_token);
    } catch (error) {
      throw new Error(parseError(error, 'Регистрация прошла, но не удалось загрузить данные текущего пользователя.'));
    }
  }, [applyToken]);

  const logout = useCallback(() => {
    clearSession();
  }, [clearSession]);

  const value = useMemo(() => ({
    isAuthenticated: Boolean(authSession?.accessToken),
    isBootstrapping,
    accessToken: authSession?.accessToken ?? '',
    profileId: authSession?.profileId ?? null,
    user: authSession?.user ?? null,
    login,
    register,
    logout,
  }), [authSession, isBootstrapping, login, logout, register]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
