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
    description: 'Refined editorial typography, soft elevation, and an accent color.',
  },
  minimal: {
    id: 'minimal',
    name: 'Minimal',
    tagline: 'Calm & Print-like',
    description: 'Hairline borders, no shadows, and generous whitespace.',
  },
  dashboard: {
    id: 'dashboard',
    name: 'Dashboard',
    tagline: 'Data-Dense Analytics',
    description: 'Data-dense cockpit layout, slim sidebar, KPI summary tiles, compact tables.',
  },
};

export const CHART_PALETTE: ChartPalette = {
  required: 'var(--chart-required)',
  preferred: 'var(--chart-preferred)',
  semantic: 'var(--chart-semantic)',
  experience: 'var(--chart-experience)',
  text: 'var(--chart-text)',
  grid: 'var(--chart-grid)',
};
