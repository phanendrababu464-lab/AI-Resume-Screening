import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import {
  loadSavedTheme,
  saveTheme,
  loadSavedPreset,
  savePreset,
  applyThemeAndPresetToDOM,
  THEME_STORAGE_KEY,
  PRESET_STORAGE_KEY,
  DEFAULT_PRESET,
} from './themeStorage.ts';

// Helper to create an in-memory Storage mock
function createStorageMock() {
  let store: Record<string, string> = {};
  return {
    getItem: vi.fn((key: string) => store[key] ?? null),
    setItem: vi.fn((key: string, val: string) => {
      store[key] = String(val);
    }),
    removeItem: vi.fn((key: string) => {
      delete store[key];
    }),
    clear: vi.fn(() => {
      store = {};
    }),
    get length() {
      return Object.keys(store).length;
    },
    key: vi.fn((i: number) => Object.keys(store)[i] ?? null),
  };
}

describe('themeStorage utils', () => {
  let storageMock: ReturnType<typeof createStorageMock>;
  let mockDocElement: {
    classList: { add: ReturnType<typeof vi.fn>; remove: ReturnType<typeof vi.fn>; contains: ReturnType<typeof vi.fn> };
    setAttribute: ReturnType<typeof vi.fn>;
    getAttribute: ReturnType<typeof vi.fn>;
  };

  beforeEach(() => {
    storageMock = createStorageMock();

    const classSet = new Set<string>();
    const attributes = new Map<string, string>();

    mockDocElement = {
      classList: {
        add: vi.fn((cls: string) => classSet.add(cls)),
        remove: vi.fn((cls: string) => classSet.delete(cls)),
        contains: vi.fn((cls: string) => classSet.has(cls)),
      },
      setAttribute: vi.fn((key: string, val: string) => attributes.set(key, val)),
      getAttribute: vi.fn((key: string) => attributes.get(key) ?? null),
    };

    // Setup global window and document mocks
    (globalThis as unknown as { window: unknown }).window = {
      localStorage: storageMock,
      matchMedia: vi.fn().mockImplementation((query: string) => ({
        matches: query === '(prefers-color-scheme: dark)',
      })),
    };

    (globalThis as unknown as { document: unknown }).document = {
      documentElement: mockDocElement,
    };
  });

  afterEach(() => {
    delete (globalThis as unknown as { window?: unknown }).window;
    delete (globalThis as unknown as { document?: unknown }).document;
    vi.restoreAllMocks();
  });

  describe('loadSavedTheme', () => {
    it('returns saved dark theme from localStorage', () => {
      storageMock.setItem(THEME_STORAGE_KEY, 'dark');
      expect(loadSavedTheme()).toBe('dark');
    });

    it('returns saved light theme from localStorage', () => {
      storageMock.setItem(THEME_STORAGE_KEY, 'light');
      expect(loadSavedTheme()).toBe('light');
    });

    it('falls back to prefers-color-scheme when localStorage is empty', () => {
      expect(loadSavedTheme()).toBe('dark');
    });

    it('falls back to light when prefers-color-scheme matches false', () => {
      (window as unknown as { matchMedia: unknown }).matchMedia = vi.fn().mockReturnValue({ matches: false });
      expect(loadSavedTheme()).toBe('light');
    });

    it('gracefully handles localStorage being disabled / throwing SecurityError', () => {
      storageMock.getItem.mockImplementation(() => {
        throw new Error('SecurityError: The operation is insecure.');
      });

      expect(() => loadSavedTheme()).not.toThrow();
      expect(loadSavedTheme()).toBe('dark'); // falls back to matchMedia
    });
  });

  describe('saveTheme', () => {
    it('saves theme to localStorage and returns true', () => {
      const success = saveTheme('dark');
      expect(success).toBe(true);
      expect(storageMock.setItem).toHaveBeenCalledWith(THEME_STORAGE_KEY, 'dark');
    });

    it('gracefully handles localStorage throwing when saving and returns false', () => {
      storageMock.setItem.mockImplementation(() => {
        throw new Error('QuotaExceededError: LocalStorage quota exceeded.');
      });

      const success = saveTheme('dark');
      expect(success).toBe(false);
    });
  });

  describe('loadSavedPreset', () => {
    it('returns saved preset when valid', () => {
      storageMock.setItem(PRESET_STORAGE_KEY, 'minimal');
      expect(loadSavedPreset()).toBe('minimal');

      storageMock.setItem(PRESET_STORAGE_KEY, 'dashboard');
      expect(loadSavedPreset()).toBe('dashboard');

      storageMock.setItem(PRESET_STORAGE_KEY, 'studio');
      expect(loadSavedPreset()).toBe('studio');
    });

    it('returns DEFAULT_PRESET (studio) when storage is empty', () => {
      expect(loadSavedPreset()).toBe(DEFAULT_PRESET);
    });

    it('returns DEFAULT_PRESET when stored value is invalid', () => {
      storageMock.setItem(PRESET_STORAGE_KEY, 'unknown_preset');
      expect(loadSavedPreset()).toBe(DEFAULT_PRESET);
    });

    it('gracefully handles localStorage throwing and returns default preset', () => {
      storageMock.getItem.mockImplementation(() => {
        throw new Error('SecurityError: Access is denied.');
      });

      expect(() => loadSavedPreset()).not.toThrow();
      expect(loadSavedPreset()).toBe(DEFAULT_PRESET);
    });
  });

  describe('savePreset', () => {
    it('saves preset to localStorage and returns true', () => {
      const success = savePreset('dashboard');
      expect(success).toBe(true);
      expect(storageMock.setItem).toHaveBeenCalledWith(PRESET_STORAGE_KEY, 'dashboard');
    });

    it('gracefully handles storage write failure and returns false', () => {
      storageMock.setItem.mockImplementation(() => {
        throw new Error('Storage write failed');
      });

      const success = savePreset('minimal');
      expect(success).toBe(false);
    });
  });

  describe('applyThemeAndPresetToDOM', () => {
    it('applies dark theme and minimal preset to DOM documentElement', () => {
      applyThemeAndPresetToDOM('dark', 'minimal');
      expect(mockDocElement.classList.add).toHaveBeenCalledWith('dark');
      expect(mockDocElement.setAttribute).toHaveBeenCalledWith('data-preset', 'minimal');
      expect(mockDocElement.setAttribute).toHaveBeenCalledWith('data-theme', 'dark');
    });

    it('applies light theme and dashboard preset to DOM documentElement', () => {
      applyThemeAndPresetToDOM('light', 'dashboard');
      expect(mockDocElement.classList.remove).toHaveBeenCalledWith('dark');
      expect(mockDocElement.setAttribute).toHaveBeenCalledWith('data-preset', 'dashboard');
      expect(mockDocElement.setAttribute).toHaveBeenCalledWith('data-theme', 'light');
    });
  });
});
