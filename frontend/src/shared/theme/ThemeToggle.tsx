import type { ReactElement } from 'react';

import { useTheme } from './ThemeProvider';

/** Accessible light/dark toggle; announces its current state via `aria-pressed`. */
export function ThemeToggle(): ReactElement {
  const { theme, toggleTheme } = useTheme();
  const isDark = theme === 'dark';

  return (
    <button
      type="button"
      className="theme-toggle"
      onClick={toggleTheme}
      aria-pressed={isDark}
      aria-label="Toggle color theme"
    >
      {isDark ? '🌙 Dark' : '☀️ Light'}
    </button>
  );
}
