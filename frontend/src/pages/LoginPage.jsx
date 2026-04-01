import { Link, Navigate, useLocation } from 'react-router-dom';
import { useState } from 'react';

import ErrorBanner from '../components/ErrorBanner.jsx';
import { useAuth } from '../auth/useAuth.js';

export default function LoginPage() {
  const { isAuthenticated, isBootstrapping, login } = useAuth();
  const location = useLocation();
  const [email, setEmail] = useState('demo@example.local');
  const [password, setPassword] = useState('demo-password-change-me');
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const fromPath = location.state?.from?.pathname ?? '/vacancies';

  if (!isBootstrapping && isAuthenticated) {
    return <Navigate to={fromPath} replace />;
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setError('');
    setIsSubmitting(true);

    try {
      await login({ email, password });
    } catch (requestError) {
      setError(requestError.message || 'Не удалось выполнить вход.');
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <section className="auth-page">
      <form className="auth-card" onSubmit={handleSubmit}>
        <h1>Вход</h1>
        <p className="auth-card__hint">Войдите, чтобы открыть рабочий профиль и страницы приложения.</p>
        {error ? <ErrorBanner message={error} /> : null}

        <label>
          Email
          <input type="email" value={email} onChange={(event) => setEmail(event.target.value)} required />
        </label>

        <label>
          Password
          <input type="password" value={password} onChange={(event) => setPassword(event.target.value)} required />
        </label>

        <button className="recommendations-toolbar__button" type="submit" disabled={isSubmitting}>
          {isSubmitting ? 'Выполняем вход...' : 'Войти'}
        </button>

        <p className="auth-card__footer">
          Нет аккаунта? <Link to="/register">Создать аккаунт</Link>
        </p>
      </form>
    </section>
  );
}
