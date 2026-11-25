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

const MIDNIGHT_BRONZE_CHART: ChartPalette = {
  required: 'var(--chart-required)',
  preferred: 'var(--chart-preferred)',
  semantic: 'var(--chart-semantic)',
  experience: 'var(--chart-experience)',
  text: 'var(--chart-text)',
  grid: 'var(--chart-grid)',
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
    dark: MIDNIGHT_BRONZE_CHART,
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
    dark: MIDNIGHT_BRONZE_CHART,
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
    dark: MIDNIGHT_BRONZE_CHART,
  },
};
