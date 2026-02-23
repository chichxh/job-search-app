import { NavLink, Outlet } from 'react-router-dom';

const navItems = [
  { to: '/vacancies', label: 'Vacancies' },
  { to: '/recommendations', label: 'Recommendations' },
  { to: '/settings', label: 'Settings' },
];

export default function Layout() {
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
