import type { ReactElement } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';

import { AuthProvider } from '../modules/auth/AuthContext';
import { LoginPage } from '../modules/auth/LoginPage';
import { ProtectedRoute } from '../modules/auth/ProtectedRoute';
import { ThemeProvider } from '../shared/theme/ThemeProvider';
import { HealthStatus } from './HealthStatus';
import { Layout } from './Layout';

/** Root component: theme, routing, and auth session wiring. */
export function App(): ReactElement {
  return (
    <ThemeProvider>
      <BrowserRouter>
        <AuthProvider>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route element={<ProtectedRoute />}>
              <Route element={<Layout />}>
                <Route path="/" element={<HealthStatus />} />
              </Route>
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </AuthProvider>
      </BrowserRouter>
    </ThemeProvider>
  );
}
