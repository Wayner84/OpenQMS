import type { ReactElement } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';

import { AuthProvider } from '../modules/auth/AuthContext';
import { LoginPage } from '../modules/auth/LoginPage';
import { ProtectedRoute } from '../modules/auth/ProtectedRoute';
import { DocumentCategoriesPage } from '../modules/documents/DocumentCategoriesPage';
import { DocumentDetailPage } from '../modules/documents/DocumentDetailPage';
import { DocumentsPage } from '../modules/documents/DocumentsPage';
import { NcrDetailPage } from '../modules/ncr/NcrDetailPage';
import { NcrsPage } from '../modules/ncr/NcrsPage';
import { CompaniesPage } from '../modules/people/CompaniesPage';
import { PeoplePage } from '../modules/people/PeoplePage';
import { AssetsPage } from '../modules/calibration/AssetsPage';
import { AssetDetailPage } from '../modules/calibration/AssetDetailPage';
import { ProductCategoriesPage } from '../modules/products/ProductCategoriesPage';
import { ProductDetailPage } from '../modules/products/ProductDetailPage';
import { ProductsPage } from '../modules/products/ProductsPage';
import { SupplierDetailPage } from '../modules/suppliers/SupplierDetailPage';
import { SuppliersPage } from '../modules/suppliers/SuppliersPage';
import { UsersPage } from '../modules/users/UsersPage';
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
                <Route path="/companies" element={<CompaniesPage />} />
                <Route path="/people" element={<PeoplePage />} />
                <Route path="/documents" element={<DocumentsPage />} />
                <Route path="/documents/:id" element={<DocumentDetailPage />} />
                <Route path="/suppliers" element={<SuppliersPage />} />
                <Route path="/suppliers/:id" element={<SupplierDetailPage />} />
                <Route path="/products" element={<ProductsPage />} />
                <Route path="/products/categories" element={<ProductCategoriesPage />} />
                <Route path="/products/:id" element={<ProductDetailPage />} />
                <Route path="/ncr" element={<NcrsPage />} />
                <Route path="/ncr/:id" element={<NcrDetailPage />} />
                <Route path="/calibration/assets" element={<AssetsPage />} />
                <Route path="/calibration/assets/:id" element={<AssetDetailPage />} />
                <Route element={<ProtectedRoute requireAdmin />}>
                  <Route path="/users" element={<UsersPage />} />
                  <Route path="/documents/categories" element={<DocumentCategoriesPage />} />
                </Route>
              </Route>
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </AuthProvider>
      </BrowserRouter>
    </ThemeProvider>
  );
}
