import { afterEach, describe, expect, it } from 'vitest';

import { clearToken, getToken, setToken } from './tokenStore';

describe('tokenStore', () => {
  afterEach(() => {
    clearToken();
  });

  it('returns null when no token has been set', () => {
    expect(getToken()).toBeNull();
  });

  it('round-trips a token through sessionStorage', () => {
    setToken('a.jwt.token');

    expect(getToken()).toBe('a.jwt.token');
    expect(window.sessionStorage.getItem('openqms-access-token')).toBe('a.jwt.token');
  });

  it('removes the token on clear', () => {
    setToken('a.jwt.token');

    clearToken();

    expect(getToken()).toBeNull();
  });
});
