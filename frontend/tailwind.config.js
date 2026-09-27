/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        graphite: {
          950: '#0a0b0c',
          900: '#0e0f10',
          850: '#121315',
          800: '#161719',
          750: '#1a1b1e',
          700: '#222327',
          600: '#2a2b2f',
          500: '#383a40',
        },
        gold: {
          DEFAULT: '#d4af5a',
          50: '#fbf8f0',
          100: '#f6eed9',
          200: '#eddcb3',
          300: '#e2bf68',
          400: '#d4af5a',
          500: '#b89445',
          600: '#9b7937',
          700: '#7a5e2c',
          800: '#544122',
          900: '#342817',
          bright: '#f0d58a',
          muted: '#a88a45',
        },
        warm: {
          50: '#faf9f5',
          100: '#f5f2ea',
          200: '#eae4d5',
          300: '#d7cfbd',
          400: '#aaa79f',
          500: '#74736e',
          600: '#575652',
          700: '#3d3c39',
          800: '#262523',
          900: '#171615',
        },
        accent: {
          green: '#4ade80',
          emerald: '#10b981',
          amber: '#f59e0b',
          rose: '#f43f5e',
          red: '#ef4444',
        }
      },
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
      },
      boxShadow: {
        'gold-subtle': '0 4px 20px -2px rgba(212, 175, 90, 0.12)',
        'gold-glow': '0 0 25px -5px rgba(212, 175, 90, 0.25)',
        'panel': '0 2px 10px rgba(0, 0, 0, 0.45)',
      },
      borderColor: {
        subtle: '#292a2b',
        'subtle-gold': 'rgba(212, 175, 90, 0.25)',
      }
    },
  },
  plugins: [],
};
