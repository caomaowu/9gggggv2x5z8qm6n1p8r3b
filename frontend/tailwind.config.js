/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'etrade-purple': '#7B61FF',
        'etrade-purple-light': '#9D8CFF',
      }
    },
  },
  plugins: [],
}
