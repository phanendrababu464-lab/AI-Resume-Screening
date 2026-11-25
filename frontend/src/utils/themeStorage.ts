import type { Theme, Preset } from '../tokens/presets.ts';

export const THEME_STORAGE_KEY = 'theme';
export const PRESET_STORAGE_KEY = 'style-preset';

export const DEFAULT_THEME: Theme = 'light';
export const DEFAULT_PRESET: Preset = 'studio';

/**
 * Safely loads the saved theme from localStorage, defaulting to light mode.
 */
export function loadSavedTheme(): Theme {
  try {
    if (typeof window !== 'undefined' && window.localStorage) {
      const saved = window.localStorage.getItem(THEME_STORAGE_KEY);
      if (saved === 'dark' || saved === 'light') {
        return saved;
      }
    }
  } catch (err) {
    // Storage access is blocked (e.g. private mode, cookies disabled)
    console.warn('localStorage is not accessible, using fallback for theme:', err);
  }

  return DEFAULT_THEME;
}

/**
 * Safely saves the theme to localStorage. Returns true if saved, false if storage is blocked.
 */
export function saveTheme(theme: Theme): boolean {
  try {
    if (typeof window !== 'undefined' && window.localStorage) {
      window.localStorage.setItem(THEME_STORAGE_KEY, theme);
      return true;
    }
  } catch (err) {
    console.warn('Failed to persist theme to localStorage:', err);
  }
  return false;
}

/**
 * Safely loads the saved style preset from localStorage, falling back to 'studio'
 * if unset, invalid, or storage is blocked.
 */
export function loadSavedPreset(): Preset {
  try {
    if (typeof window !== 'undefined' && window.localStorage) {
      const saved = window.localStorage.getItem(PRESET_STORAGE_KEY);
      if (saved === 'studio' || saved === 'minimal' || saved === 'dashboard') {
        return saved;
      }
    }
  } catch (err) {
    console.warn('localStorage is not accessible, using default preset:', err);
  }
  return DEFAULT_PRESET;
}

/**
 * Safely saves the style preset to localStorage. Returns true if saved, false if storage is blocked.
 */
export function savePreset(preset: Preset): boolean {
  try {
    if (typeof window !== 'undefined' && window.localStorage) {
      window.localStorage.setItem(PRESET_STORAGE_KEY, preset);
      return true;
    }
  } catch (err) {
    console.warn('Failed to persist style preset to localStorage:', err);
  }
  return false;
}

/**
 * Updates DOM attributes to activate the theme and preset classes.
 */
export function applyThemeAndPresetToDOM(theme: Theme, preset: Preset): void {
  if (typeof document === 'undefined') return;

  const root = document.documentElement;
  if (theme === 'dark') {
    root.classList.add('dark');
  } else {
    root.classList.remove('dark');
  }

  root.setAttribute('data-preset', preset);
  root.setAttribute('data-theme', theme);
}
