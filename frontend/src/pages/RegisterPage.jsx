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
      <form className="auth-card" onSubmit={handleSubmit}>
        <h1>Register</h1>
        <p className="auth-card__hint">После регистрации автоматически создастся профиль и откроется приложение.</p>
        {error ? <ErrorBanner message={error} /> : null}

        <label>
          Email
          <input type="email" value={email} onChange={(event) => setEmail(event.target.value)} required />
        </label>

        <label>
          Password (min 8 chars)
          <input type="password" minLength={8} value={password} onChange={(event) => setPassword(event.target.value)} required />
        </label>

        <button className="recommendations-toolbar__button" type="submit" disabled={isSubmitting}>
          {isSubmitting ? 'Creating account...' : 'Create account'}
        </button>

        <p className="auth-card__footer">
          Уже есть аккаунт? <Link to="/login">Войти</Link>
        </p>
      </form>
    </section>
  );
}
