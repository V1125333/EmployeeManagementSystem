/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        olive: {
          DEFAULT: '#66785F',
          light: '#f3f5ef',
          mid: '#dde3d4',
          dark: '#4d5c47',
        },
        sage: {
          DEFAULT: '#A3B18A',
          light: '#c2ceab',
        },
        warm: {
          bg: '#F7F6F2',
          card: '#FEFEFC',
        },
        hover: {
          bg: '#EEF1E8',
        },
        status: {
          success: '#7BAE7F',
          warning: '#D6A85F',
          error: '#D97C7C',
          info: '#7E9BB7',
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
        'card-md': '0 4px 12px rgba(47,52,55,0.06), 0 1px 3px rgba(47,52,55,0.04)',
      },
    },
  },
  plugins: [],
}
