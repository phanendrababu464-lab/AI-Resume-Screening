/* eslint-disable react-refresh/only-export-components */
import React, { createContext, useContext, useEffect, useState } from 'react';
import type { Theme, Preset, ChartPalette } from '../tokens/presets.ts';
import { CHART_PALETTES } from '../tokens/presets.ts';
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

  // Sync to DOM and localStorage whenever theme or preset changes
  useEffect(() => {
    applyThemeAndPresetToDOM(theme, preset);
    saveTheme(theme);
    savePreset(preset);
  }, [theme, preset]);

  const toggleTheme = () => {
    setThemeState((prev) => (prev === 'light' ? 'dark' : 'light'));
  };

  const setTheme = (newTheme: Theme) => {
    setThemeState(newTheme);
  };

  const setPreset = (newPreset: Preset) => {
    setPresetState(newPreset);
  };

  const chartPalette = CHART_PALETTES[preset][theme];

  return (
    <ThemeContext.Provider
      value={{
        theme,
        preset,
        toggleTheme,
        setTheme,
        setPreset,
        chartPalette,
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
