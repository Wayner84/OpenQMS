/**
 * Access-token persistence, read by shared/api/client.ts to attach the
 * `Authorization` header. Backed by `sessionStorage` (not `localStorage`): the
 * backend issues short-lived (60-minute default), non-refreshable access tokens
 * with no server-side session table (see
 * docs/DecisionLog.md#2026-07-25-authentication-password-hashing-and-token-revocation-strategy),
 * so the frontend mirrors that "don't keep more standing exposure than necessary"
 * posture by clearing the token when the tab/browser closes rather than persisting
 * it indefinitely across sessions.
 */

const STORAGE_KEY = 'openqms-access-token';

export function getToken(): string | null {
  return window.sessionStorage.getItem(STORAGE_KEY);
}

export function setToken(token: string): void {
  window.sessionStorage.setItem(STORAGE_KEY, token);
}

export function clearToken(): void {
  window.sessionStorage.removeItem(STORAGE_KEY);
}
