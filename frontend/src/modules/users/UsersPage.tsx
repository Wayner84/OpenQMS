import { useCallback, useEffect, useRef, useState } from 'react';
import type { FormEvent, ReactElement } from 'react';

import { getErrorDetail } from '../../shared/api/client';
import type { User, UserRole } from '../auth/types';
import { createUser, listUsers, updateUser } from './api';

const DEFAULT_PAGE_SIZE = 20;

interface NewUserForm {
  fullName: string;
  email: string;
  password: string;
  role: UserRole;
}

const emptyForm: NewUserForm = { fullName: '', email: '', password: '', role: 'member' };

/** Admin-only user management: create, list (paginated), and deactivate/reactivate/re-role users. */
export function UsersPage({ pageSize = DEFAULT_PAGE_SIZE }: { pageSize?: number }): ReactElement {
  const [users, setUsers] = useState<User[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [pendingIds, setPendingIds] = useState<ReadonlySet<string>>(new Set());
  const [form, setForm] = useState<NewUserForm>(emptyForm);
  const [creating, setCreating] = useState(false);
  const mountedRef = useRef(true);

  useEffect(() => {
    // Set (not just read) on every (re-)mount, not only cleared on unmount: React 18
    // StrictMode double-invokes this effect in development (mount, cleanup, mount
    // again) to surface missing-cleanup bugs. Without resetting to `true` here, the
    // cleanup from that simulated first mount leaves this permanently `false`, so
    // every subsequent `if (mountedRef.current) setState(...)` below silently no-ops
    // — including the ones that turn off the initial loading state.
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const loadPage = useCallback(
    async (nextOffset: number) => {
      setLoading(true);
      setLoadError(null);
      try {
        const page = await listUsers({ limit: pageSize, offset: nextOffset });
        if (mountedRef.current) {
          setUsers(page.items);
          setTotal(page.total);
          setOffset(nextOffset);
        }
      } catch {
        if (mountedRef.current) {
          setLoadError('Could not load users. Please try again.');
        }
      } finally {
        if (mountedRef.current) {
          setLoading(false);
        }
      }
    },
    [pageSize],
  );

  useEffect(() => {
    void loadPage(0);
  }, [loadPage]);

  const handleCreate = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    setActionError(null);
    setCreating(true);
    void (async () => {
      try {
        await createUser({
          full_name: form.fullName,
          email: form.email,
          password: form.password,
          role: form.role,
        });
        if (mountedRef.current) {
          setForm(emptyForm);
        }
        await loadPage(0);
      } catch (err) {
        if (mountedRef.current) {
          setActionError(getErrorDetail(err) ?? 'Could not create the user. Please try again.');
        }
      } finally {
        if (mountedRef.current) {
          setCreating(false);
        }
      }
    })();
  };

  const handleToggleActive = (user: User): void => {
    setActionError(null);
    setPendingIds((current) => new Set(current).add(user.id));
    void (async () => {
      try {
        await updateUser(user.id, { is_active: !user.is_active });
        await loadPage(offset);
      } catch (err) {
        if (mountedRef.current) {
          setActionError(getErrorDetail(err) ?? 'Could not update the user. Please try again.');
        }
      } finally {
        if (mountedRef.current) {
          setPendingIds((current) => {
            const next = new Set(current);
            next.delete(user.id);
            return next;
          });
        }
      }
    })();
  };

  const handleRoleChange = (user: User, role: UserRole): void => {
    if (role === user.role) {
      return;
    }
    setActionError(null);
    setPendingIds((current) => new Set(current).add(user.id));
    void (async () => {
      try {
        await updateUser(user.id, { role });
        await loadPage(offset);
      } catch (err) {
        if (mountedRef.current) {
          setActionError(getErrorDetail(err) ?? 'Could not update the user. Please try again.');
        }
      } finally {
        if (mountedRef.current) {
          setPendingIds((current) => {
            const next = new Set(current);
            next.delete(user.id);
            return next;
          });
        }
      }
    })();
  };

  const canGoPrevious = offset > 0;
  const canGoNext = offset + users.length < total;

  return (
    <section>
      <h2>User management</h2>
      {actionError && (
        <p role="alert" className="auth-form__error">
          {actionError}
        </p>
      )}

      <form className="auth-form" onSubmit={handleCreate} aria-label="Create user">
        <h3>Create user</h3>
        <div className="form-field">
          <label htmlFor="new-user-name">Full name</label>
          <input
            id="new-user-name"
            required
            value={form.fullName}
            onChange={(event) => {
              setForm((current) => ({ ...current, fullName: event.target.value }));
            }}
          />
        </div>
        <div className="form-field">
          <label htmlFor="new-user-email">Email</label>
          <input
            id="new-user-email"
            type="email"
            required
            value={form.email}
            onChange={(event) => {
              setForm((current) => ({ ...current, email: event.target.value }));
            }}
          />
        </div>
        <div className="form-field">
          <label htmlFor="new-user-password">Password</label>
          <input
            id="new-user-password"
            type="password"
            required
            value={form.password}
            onChange={(event) => {
              setForm((current) => ({ ...current, password: event.target.value }));
            }}
          />
        </div>
        <div className="form-field">
          <label htmlFor="new-user-role">Role</label>
          <select
            id="new-user-role"
            value={form.role}
            onChange={(event) => {
              setForm((current) => ({ ...current, role: event.target.value as UserRole }));
            }}
          >
            <option value="member">Member</option>
            <option value="admin">Admin</option>
          </select>
        </div>
        <button type="submit" className="button button--primary" disabled={creating}>
          {creating ? 'Creating…' : 'Create user'}
        </button>
      </form>

      {loading && (
        <p role="status" className="auth-loading">
          Loading…
        </p>
      )}
      {loadError && (
        <p role="alert" className="auth-form__error">
          {loadError}
        </p>
      )}

      {!loading && !loadError && (
        <>
          <div className="data-table-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th scope="col">Name</th>
                  <th scope="col">Email</th>
                  <th scope="col">Role</th>
                  <th scope="col">Status</th>
                  <th scope="col">Actions</th>
                </tr>
              </thead>
              <tbody>
                {users.map((user) => {
                  const isPending = pendingIds.has(user.id);
                  return (
                    <tr key={user.id}>
                      <td>{user.full_name}</td>
                      <td>{user.email}</td>
                      <td>
                        <label className="visually-hidden" htmlFor={`role-${user.id}`}>
                          Role for {user.full_name}
                        </label>
                        <select
                          id={`role-${user.id}`}
                          value={user.role}
                          disabled={isPending}
                          onChange={(event) => {
                            handleRoleChange(user, event.target.value as UserRole);
                          }}
                        >
                          <option value="member">Member</option>
                          <option value="admin">Admin</option>
                        </select>
                      </td>
                      <td>{user.is_active ? 'Active' : 'Inactive'}</td>
                      <td>
                        <button
                          type="button"
                          className="button"
                          disabled={isPending}
                          onClick={() => {
                            handleToggleActive(user);
                          }}
                        >
                          {user.is_active
                            ? `Deactivate ${user.full_name}`
                            : `Reactivate ${user.full_name}`}
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <div className="app-header__actions">
            <button
              type="button"
              className="button"
              disabled={!canGoPrevious}
              onClick={() => {
                void loadPage(Math.max(0, offset - pageSize));
              }}
            >
              Previous
            </button>
            <button
              type="button"
              className="button"
              disabled={!canGoNext}
              onClick={() => {
                void loadPage(offset + pageSize);
              }}
            >
              Next
            </button>
          </div>
        </>
      )}
    </section>
  );
}
