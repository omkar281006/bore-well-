import { useCallback, useEffect, useState } from 'react';
import { refreshChartColors } from '../charts/canvas.js';

function initialTheme() {
  try {
    const saved = localStorage.getItem('bw-theme');
    if (saved) return saved;
  } catch (e) { /* storage blocked */ }
  return document.documentElement.getAttribute('data-theme') || 'dark';
}

/** Light / dark theme stored on <html data-theme> and remembered in localStorage. */
export function useTheme() {
  const [theme, setTheme] = useState(initialTheme);
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    try { localStorage.setItem('bw-theme', theme); } catch (e) { /* storage blocked */ }
    refreshChartColors();
  }, [theme]);
  const toggle = useCallback(() => setTheme((t) => (t === 'light' ? 'dark' : 'light')), []);
  return { theme, isLight: theme === 'light', toggle };
}
