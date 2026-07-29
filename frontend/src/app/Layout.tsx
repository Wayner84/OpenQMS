import type { ReactElement } from 'react';
import { NavLink, Outlet } from 'react-router-dom';

import { useAuth } from '../modules/auth/AuthContext';
import { ThemeToggle } from '../shared/theme/ThemeToggle';

/** The authenticated application shell: header (nav, theme toggle, logout) plus routed content. */
export function Layout(): ReactElement {
  const { user, logout } = useAuth();

  return (
    <div className="app-shell">
      <header className="app-header">
        <h1>openQMS</h1>
        <nav className="app-nav" aria-label="Main navigation">
          <NavLink to="/">Dashboard</NavLink>
          <NavLink to="/companies">Companies</NavLink>
          <NavLink to="/people">People</NavLink>
          <NavLink to="/documents">Documents</NavLink>
          <NavLink to="/suppliers">Suppliers</NavLink>
          <NavLink to="/products">Products</NavLink>
          {user?.role === 'admin' && <NavLink to="/users">Users</NavLink>}
        </nav>
        <div className="app-header__actions">
          <ThemeToggle />
          {user && (
            <button
              type="button"
              className="logout-button"
              onClick={() => {
                void logout();
              }}
            >
              Log out ({user.full_name})
            </button>
          )}
        </div>
      </header>
      <main className="app-main">
        <Outlet />
      </main>
    </div>
  );
}
