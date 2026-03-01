/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Outfit', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Helvetica Neue', 'Arial', 'sans-serif'],
      },
      colors: {
        cream: '#F8F7F2',
        primary: {
          50: '#F9F8F5',
          100: '#f0eeea',
          500: '#000000',
          600: '#000000',
        },
      },
    },
  },
  plugins: [],
}
