import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';

import { useAuth } from '../auth/useAuth.js';

const navItems = [
  { to: '/vacancies', label: 'Вакансии', description: 'Импорт и трекинг позиций' },
  { to: '/recommendations', label: 'Рекомендации', description: 'Ранжирование и мэтчинг' },
  { to: '/applications', label: 'Отклики', description: 'Воронка и статусы' },
  { to: '/settings', label: 'Настройки', description: 'Профиль и источники данных' },
];

const pageTitles = {
  '/vacancies': 'Работа с вакансиями',
  '/recommendations': 'Рекомендации',
  '/applications': 'Воронка откликов',
  '/settings': 'Настройки и профиль',
};

const pageSubtitles = {
  '/vacancies': 'Собирайте вакансии, фильтруйте сигнал и планируйте следующие шаги.',
  '/recommendations': 'Приоритизируйте вакансии по сигналам мэтчинга профиля.',
  '/applications': 'Ведите процесс от сохранения вакансии до оффера.',
  '/settings': 'Поддерживайте качество профиля и данных документов.',
};

export default function Layout() {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, profileId, logout } = useAuth();

  const activeSection = navItems.find((item) => location.pathname.startsWith(item.to));
  const pageTitle = pageTitles[activeSection?.to] ?? 'Рабочее пространство поиска работы';
  const pageSubtitle = pageSubtitles[activeSection?.to] ?? 'Единое пространство для управляемого поиска работы.';

  function handleLogout() {
    logout();
    navigate('/login', { replace: true });
  }

  return (
    <div className="app-shell">
      <aside className="app-shell__sidebar">
        <div className="app-shell__brand-block">
          <p className="app-shell__eyebrow">Рабочее пространство</p>
          <p className="app-shell__brand">Поиск работы OS</p>
        </div>

        <nav>
          <ul className="app-shell__nav-list">
            {navItems.map((item) => (
              <li key={item.to}>
                <NavLink
                  to={item.to}
                  className={({ isActive }) =>
                    `app-shell__nav-link${isActive ? ' app-shell__nav-link--active' : ''}`
                  }
                >
                  <span>{item.label}</span>
                  <small>{item.description}</small>
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
      </aside>

      <div className="app-shell__content">
        <header className="app-shell__topbar">
          <div>
            <p className="app-shell__title">{pageTitle}</p>
            <p className="app-shell__subtitle">{pageSubtitle}</p>
          </div>
          <div className="app-shell__user-box">
            <p>{user?.email ?? '—'}</p>
            <p>Профиль #{profileId ?? '—'}</p>
            <button className="button button--secondary button--sm" type="button" onClick={handleLogout}>Выйти</button>
          </div>
        </header>

        <main className="app-shell__main">
          <div className="app-shell__page-container">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
