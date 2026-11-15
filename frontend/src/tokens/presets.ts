export type Theme = 'light' | 'dark';
export type Preset = 'studio' | 'minimal' | 'dashboard';

export interface ChartPalette {
  required: string;
  preferred: string;
  semantic: string;
  experience: string;
  text: string;
  grid: string;
}

export interface PresetMeta {
  id: Preset;
  name: string;
  tagline: string;
  description: string;
}

export const PRESETS: Record<Preset, PresetMeta> = {
  studio: {
    id: 'studio',
    name: 'Studio',
    tagline: 'Refined & Editorial',
    description: 'Refined editorial typography, soft elevation, and a single indigo accent.',
  },
  minimal: {
    id: 'minimal',
    name: 'Minimal',
    tagline: 'Calm & Print-like',
    description: 'Near-monochrome, hairline borders, no shadows, generous whitespace, and muted ink accent.',
  },
  dashboard: {
    id: 'dashboard',
    name: 'Dashboard',
    tagline: 'Data-Dense Analytics',
    description: 'Data-dense cockpit layout, slim sidebar, KPI summary tiles, compact tables, and rich categorical palette.',
  },
};

export const CHART_PALETTES: Record<Preset, Record<Theme, ChartPalette>> = {
  studio: {
    light: {
      required: '#6366f1', // Indigo 500
      preferred: '#a855f7', // Purple 500
      semantic: '#10b981', // Emerald 500
      experience: '#f59e0b', // Amber 500
      text: '#475569', // Slate 600
      grid: '#e2e8f0', // Slate 200
    },
    dark: {
      required: '#818cf8', // Indigo 400
      preferred: '#c084fc', // Purple 400
      semantic: '#34d399', // Emerald 400
      experience: '#fbbf24', // Amber 400
      text: '#cbd5e1', // Slate 300
      grid: '#334155', // Slate 700
    },
  },
  minimal: {
    light: {
      required: '#18181b', // Zinc 900 (High contrast ink)
      preferred: '#52525b', // Zinc 600
      semantic: '#71717a', // Zinc 500
      experience: '#a1a1aa', // Zinc 400
      text: '#52525b', // Zinc 600
      grid: '#e4e4e7', // Zinc 200 hairline
    },
    dark: {
      required: '#fafafa', // Zinc 50 (Crisp white ink)
      preferred: '#d4d4d8', // Zinc 300
      semantic: '#a1a1aa', // Zinc 400
      experience: '#52525b', // Zinc 600
      text: '#d4d4d8', // Zinc 300
      grid: '#27272a', // Zinc 800 hairline
    },
  },
  dashboard: {
    light: {
      required: '#2563eb', // Royal Blue
      preferred: '#0d9488', // Teal 600
      semantic: '#7c3aed', // Violet 600
      experience: '#ea580c', // Tangerine 600
      text: '#334155', // Slate 700
      grid: '#cbd5e1', // Slate 300
    },
    dark: {
      required: '#38bdf8', // Sky 400 (High-tech cyan)
      preferred: '#2dd4bf', // Teal 400
      semantic: '#a78bfa', // Violet 400
      experience: '#fb923c', // Orange 400
      text: '#cbd5e1', // Slate 300
      grid: '#1e293b', // Slate 800
    },
  },
};
