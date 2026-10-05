import type { Config } from 'tailwindcss';
const config: Config = {
  content: ['./app/**/*.{ts,tsx}', './components/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        ink: { DEFAULT: '#14232f', 700: '#26394a', 500: '#4a5d6c', 400: '#6b7c89', 300: '#9aa7b1', 200: '#cfd6db', 100: '#e7ebee', 50: '#f3f5f6' },
        paper: '#f7f6f2',
        brand: { DEFAULT: '#0b5d4b', 700: '#0a4d3f', 600: '#0e6e58', 100: '#d7ebe5', 50: '#eef7f4' },
        saffron: { DEFAULT: '#b7791f', 100: '#faecd0', 50: '#fdf6e7' },
        alert: { DEFAULT: '#a12b2b', 50: '#fbeeee' },
      },
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', '-apple-system', 'Segoe UI', 'Roboto', 'sans-serif'],
        serif: ['"Source Serif 4"', 'Georgia', 'Cambria', '"Times New Roman"', 'serif'],
      },
      boxShadow: { card: '0 1px 2px rgba(20,35,47,.06), 0 1px 1px rgba(20,35,47,.04)' },
      keyframes: { slide: { from: { transform: 'translateX(24px)', opacity: '0' }, to: { transform: 'none', opacity: '1' } }, fade: { from: { opacity: '0' }, to: { opacity: '1' } } },
      animation: { slide: 'slide .22s ease-out', fade: 'fade .2s ease-out' },
    },
  },
  plugins: [],
};
export default config;
