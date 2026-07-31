/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      gridTemplateColumns: {
        13: 'repeat(13, minmax(0, 1fr))',
      },
      fontFamily: {
        display: ['Georgia', 'serif'],
        body: ['Avenir Next', 'Segoe UI', 'sans-serif'],
      },
    },
  },
  plugins: [],
};
