/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {
      colors: {
        'background': '#0D1117',
        'panel': '#161B22',
        'border': '#30363d',
        'neon-blue': '#00BFFF',
        'neon-red': '#FF3131',
      },
      fontFamily: {
        sans: ['Inter', 'sans-serif'],
      },
       animation: {
        'fade-in': 'fadeIn 0.5s ease-in-out',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
      },
    },
  },
  plugins: [],
}