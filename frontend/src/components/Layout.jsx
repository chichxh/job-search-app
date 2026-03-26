import { NavLink, Outlet, useNavigate } from 'react-router-dom';

import { useAuth } from '../auth/useAuth.js';

const navItems = [
  { to: '/vacancies', label: 'Vacancies' },
  { to: '/recommendations', label: 'Recommendations' },
  { to: '/applications', label: 'Applications' },
  { to: '/settings', label: 'Settings' },
];

export default function Layout() {
  const navigate = useNavigate();
  const { user, profileId, logout } = useAuth();

  function handleLogout() {
    logout();
    navigate('/login', { replace: true });
  }

  return (
    <div className="layout">
      <header className="layout__header">
        <div className="layout__container layout__header-inner">
          <p className="layout__brand">Job Search</p>
          <nav>
            <ul className="layout__nav-list">
              {navItems.map((item) => (
                <li key={item.to}>
                  <NavLink
                    to={item.to}
                    className={({ isActive }) =>
                      `layout__nav-link${isActive ? ' layout__nav-link--active' : ''}`
                    }
                  >
                    {item.label}
                  </NavLink>
                </li>
              ))}
            </ul>
          </nav>
          <div className="layout__user-box">
            <p>{user?.email ?? '—'} · profile #{profileId ?? '—'}</p>
            <button className="layout__logout" type="button" onClick={handleLogout}>Logout</button>
          </div>
        </div>
      </header>

      <main className="layout__main">
        <div className="layout__container">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
