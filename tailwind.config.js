/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        accent: {
          DEFAULT: 'var(--color-accent)',
          light: 'var(--color-accent-light)',
          mid: 'var(--color-accent-mid)',
          dark: 'var(--color-accent-dark)',
        },
        olive: {
          DEFAULT: 'var(--color-accent)',
          light: 'var(--color-accent-light)',
          mid: 'var(--color-accent-mid)',
          dark: 'var(--color-accent-dark)',
        },
        sage: {
          DEFAULT: 'var(--color-brand-navy)',
          light: 'color-mix(in srgb, var(--color-brand-navy) 10%, var(--color-brand-surface))',
        },
        warm: {
          bg: 'var(--color-brand-canvas)',
          card: 'var(--color-brand-surface)',
        },
        hover: {
          bg: 'var(--color-bg-hover)',
        },
        status: {
          success: 'var(--color-status-success)',
          warning: 'var(--color-status-warning)',
          error: 'var(--color-status-error)',
          info: 'var(--color-status-info)',
        },
      },
      fontFamily: {
        sans: ['"Source Sans 3"', 'system-ui', 'sans-serif'],
      },
      borderRadius: {
        card: '14px',
        btn: '10px',
      },
      boxShadow: {
        card: '0 1px 3px color-mix(in srgb, var(--color-brand-navy) 4%, transparent), 0 1px 2px color-mix(in srgb, var(--color-brand-navy) 2%, transparent)',
        'card-md': '0 8px 24px color-mix(in srgb, var(--color-brand-navy) 8%, transparent), 0 1px 3px color-mix(in srgb, var(--color-brand-navy) 4%, transparent)',
      },
    },
  },
  plugins: [],
}
