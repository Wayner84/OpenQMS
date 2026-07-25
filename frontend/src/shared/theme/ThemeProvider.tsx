import { createContext, useContext, useEffect, useMemo, useState } from 'react';
import type { ReactElement, ReactNode } from 'react';

export type Theme = 'light' | 'dark';

interface ThemeContextValue {
  /** The theme actually applied: the user's explicit choice, or the OS preference. */
  theme: Theme;
  toggleTheme: () => void;
}

const STORAGE_KEY = 'openqms-theme';

const ThemeContext = createContext<ThemeContextValue | undefined>(undefined);

// Mirrored as an inline script in index.html so the theme applies before this module
// loads, avoiding a flash of the wrong theme; keep both in sync if this logic changes.
function readStoredTheme(): Theme | null {
  const stored = window.localStorage.getItem(STORAGE_KEY);
  return stored === 'light' || stored === 'dark' ? stored : null;
}

function systemPrefersDark(): boolean {
  return window.matchMedia('(prefers-color-scheme: dark)').matches;
}

/**
 * Applies the light/dark theme respecting the OS preference by default, with an
 * explicit user toggle that overrides it and persists across visits.
 */
export function ThemeProvider({ children }: { children: ReactNode }): ReactElement {
  const [override, setOverride] = useState<Theme | null>(() => readStoredTheme());
  const [prefersDark, setPrefersDark] = useState<boolean>(() => systemPrefersDark());

  useEffect(() => {
    const media = window.matchMedia('(prefers-color-scheme: dark)');
    const handleChange = (event: MediaQueryListEvent): void => {
      setPrefersDark(event.matches);
    };
    media.addEventListener('change', handleChange);
    return () => {
      media.removeEventListener('change', handleChange);
    };
  }, []);

  const theme: Theme = override ?? (prefersDark ? 'dark' : 'light');

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);

  const value = useMemo<ThemeContextValue>(
    () => ({
      theme,
      toggleTheme: () => {
        const next: Theme = theme === 'dark' ? 'light' : 'dark';
        window.localStorage.setItem(STORAGE_KEY, next);
        setOverride(next);
      },
    }),
    [theme],
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeContextValue {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error('useTheme must be used within a ThemeProvider');
  }
  return context;
}
