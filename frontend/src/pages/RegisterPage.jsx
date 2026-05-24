import { Link, Navigate } from 'react-router-dom';
import { useState } from 'react';

import ErrorBanner from '../components/ErrorBanner.jsx';
import { useAuth } from '../auth/useAuth.js';

export default function RegisterPage() {
  const { isAuthenticated, isBootstrapping, register } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  if (!isBootstrapping && isAuthenticated) {
    return <Navigate to="/vacancies" replace />;
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setError('');
    setIsSubmitting(true);

    try {
      await register({ email, password });
    } catch (requestError) {
      setError(requestError.message || 'Не удалось создать аккаунт.');
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <section className="auth-page">
      <div className="auth-layout">
        <aside className="auth-layout__side">
          <p className="auth-layout__eyebrow">Начните работу</p>
          <h1>Создайте аккаунт</h1>
          <p className="auth-layout__copy">После регистрации вы сразу попадёте в рабочий флоу: вакансии → ранжирование → отклики.</p>
          <ul className="auth-layout__list">
            <li>Единый профиль для рекомендаций и документов</li>
            <li>Быстрый старт без дополнительной настройки</li>
            <li>Чистый интерфейс для ежедневной работы</li>
          </ul>
        </aside>

        <form className="auth-card" onSubmit={handleSubmit}>
          <p className="auth-card__eyebrow">Создать аккаунт</p>
          <h2>Регистрация</h2>
          <p className="auth-card__hint">Минимум полей — максимум фокуса на поиске работы.</p>
          {error ? <ErrorBanner message={error} /> : null}

          <label>
            Email
            <input type="email" value={email} onChange={(event) => setEmail(event.target.value)} required />
          </label>

          <label>
            Пароль (минимум 8 символов)
            <input type="password" minLength={8} value={password} onChange={(event) => setPassword(event.target.value)} required />
          </label>

          <button className="button" type="submit" disabled={isSubmitting}>
            {isSubmitting ? 'Создаём аккаунт...' : 'Создать аккаунт'}
          </button>

          <p className="auth-card__footer">
            Уже есть аккаунт? <Link className="inline-link" to="/login">Войти</Link>
          </p>
        </form>
      </div>
    </section>
  );
}
