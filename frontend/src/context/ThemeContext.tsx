/* eslint-disable react-refresh/only-export-components */
import React, { createContext, useContext, useEffect, useState } from 'react';
import type { Theme, Preset, ChartPalette } from '../tokens/presets.ts';
import { CHART_PALETTE } from '../tokens/presets.ts';
import {
  loadSavedTheme,
  saveTheme,
  loadSavedPreset,
  savePreset,
  applyThemeAndPresetToDOM,
} from '../utils/themeStorage.ts';

interface ThemeContextType {
  theme: Theme;
  preset: Preset;
  toggleTheme: () => void;
  setTheme: (theme: Theme) => void;
  setPreset: (preset: Preset) => void;
  chartPalette: ChartPalette;
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

export const ThemeProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [theme, setThemeState] = useState<Theme>(loadSavedTheme);
  const [preset, setPresetState] = useState<Preset>(loadSavedPreset);

  // Keep the default separate from explicitly saved theme choices.
  useEffect(() => {
    applyThemeAndPresetToDOM(theme, preset);
    savePreset(preset);
  }, [theme, preset]);

  const setTheme = (newTheme: Theme) => {
    setThemeState(newTheme);
    saveTheme(newTheme);
  };

  const toggleTheme = () => {
    setTheme(theme === 'light' ? 'dark' : 'light');
  };

  const setPreset = (newPreset: Preset) => {
    setPresetState(newPreset);
  };

  return (
    <ThemeContext.Provider
      value={{
        theme,
        preset,
        toggleTheme,
        setTheme,
        setPreset,
        chartPalette: CHART_PALETTE,
      }}
    >
      {children}
    </ThemeContext.Provider>
  );
};

export const useTheme = (): ThemeContextType => {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error('useTheme must be used within a ThemeProvider');
  }
  return context;
};
