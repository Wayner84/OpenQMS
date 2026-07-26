import type { ReactElement } from 'react';
import { Navigate, Outlet, useLocation } from 'react-router-dom';

import { useAuth } from './AuthContext';

/**
 * Gatekeeps nested routes: redirects to `/login` (remembering where the user was
 * headed) while unauthenticated, and to `/` if `requireAdmin` is set and the
 * current user isn't an admin. Client-side only — every admin-only *action* is
 * re-enforced by the backend regardless of what this component renders.
 */
export function ProtectedRoute({ requireAdmin = false }: { requireAdmin?: boolean }): ReactElement {
  const { status, user } = useAuth();
  const location = useLocation();

  if (status === 'loading') {
    return (
      <p role="status" className="auth-loading">
        Loading…
      </p>
    );
  }

  if (status === 'unauthenticated' || !user) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  if (requireAdmin && user.role !== 'admin') {
    return <Navigate to="/" replace />;
  }

  return <Outlet />;
}
