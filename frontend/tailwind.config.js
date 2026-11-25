const token = (name) => `color-mix(in srgb, var(--${name}) calc(<alpha-value> * 100%), transparent)`;

/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
      },
      colors: {
        theme: {
          canvas: token('bg-app'),
          surface: token('bg-card'),
          subtle: token('bg-card-subtle'),
          border: token('border-color'),
          ink: token('text-primary'),
          muted: token('text-muted'),
          'secondary-text': token('text-secondary'),
          primary: token('color-accent'),
          secondary: token('color-accent-secondary'),
          hover: token('color-accent-hover'),
          tint: token('color-accent-subtle'),
          'on-accent': token('text-on-accent'),
        },
      },
      borderRadius: {
        'card': '14px',
      },
      boxShadow: {
        'card': '0 1px 3px 0 rgba(0, 0, 0, 0.05), 0 1px 2px -1px rgba(0, 0, 0, 0.05)',
        'card-hover': '0 4px 6px -1px rgba(0, 0, 0, 0.07), 0 2px 4px -2px rgba(0, 0, 0, 0.05)',
      },
    },
  },
  plugins: [],
}
