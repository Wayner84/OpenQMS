/**
 * A tiny pub/sub so `shared/api/client.ts` (which knows nothing about React) can
 * notify `modules/auth/AuthContext.tsx` when an authenticated request comes back
 * `401` mid-session (expired, revoked-by-logout-elsewhere, or the user was
 * deactivated) — cases the initial mount check in AuthContext can't catch because
 * they happen after the session was already validated once.
 */

type UnauthorizedListener = () => void;

const listeners = new Set<UnauthorizedListener>();

/** Subscribes to session-invalidated notifications; returns an unsubscribe function. */
export function onUnauthorized(listener: UnauthorizedListener): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

/** Notifies all subscribers that the current session is no longer valid. */
export function emitUnauthorized(): void {
  for (const listener of listeners) {
    listener();
  }
}
