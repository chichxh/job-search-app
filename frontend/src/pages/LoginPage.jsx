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
      <div className="auth-layout">
        <aside className="auth-layout__side">
          <p className="auth-layout__eyebrow">Job Search OS</p>
          <h1>Вход в рабочее пространство</h1>
          <p className="auth-layout__copy">Продолжайте поиск вакансий, обновляйте ranking и ведите воронку откликов в одном месте.</p>
          <ul className="auth-layout__list">
            <li>Актуальные вакансии и фильтры без лишнего шума</li>
            <li>Понятный next step для каждой рекомендации</li>
            <li>Связка документов и статусов откликов</li>
          </ul>
        </aside>

        <form className="auth-card" onSubmit={handleSubmit}>
          <p className="auth-card__eyebrow">Sign in</p>
          <h2>С возвращением</h2>
          <p className="auth-card__hint">Используйте аккаунт, чтобы открыть профиль и рабочие разделы приложения.</p>
          {error ? <ErrorBanner message={error} /> : null}

          <label>
            Email
            <input type="email" value={email} onChange={(event) => setEmail(event.target.value)} required />
          </label>

          <label>
            Password
            <input type="password" value={password} onChange={(event) => setPassword(event.target.value)} required />
          </label>

          <button className="button" type="submit" disabled={isSubmitting}>
            {isSubmitting ? 'Выполняем вход...' : 'Войти'}
          </button>

          <p className="auth-card__footer">
            Нет аккаунта? <Link className="inline-link" to="/register">Создать аккаунт</Link>
          </p>
        </form>
      </div>
    </section>
  );
}
