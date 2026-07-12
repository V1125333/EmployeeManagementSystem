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
          DEFAULT: '#F5A23A',
          light: '#FFF4E8',
          mid: '#F9D7A6',
          dark: '#D97706',
        },
        sage: {
          DEFAULT: '#252B3A',
          light: '#E7E9EE',
        },
        warm: {
          bg: '#F7F6F2',
          card: '#FEFEFC',
        },
        hover: {
          bg: '#FFF7ED',
        },
        status: {
          success: '#1F9D55',
          warning: '#F5A23A',
          error: '#DC2626',
          info: '#2563EB',
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
        card: '0 1px 3px rgba(47,52,55,0.04), 0 1px 2px rgba(47,52,55,0.02)',
        'card-md': '0 8px 24px rgba(37,43,58,0.08), 0 1px 3px rgba(37,43,58,0.04)',
      },
    },
  },
  plugins: [],
}
