/** @type {import('tailwindcss').Config} */
export default {
  content: ['./src/**/*.{html,js,svelte,ts}'],
  theme: {
    extend: {
      colors: {
        'lilac-xlight': '#e6d7ff',
        'lilac-light': '#e7d1ff',
        'lilac-medium': '#e1c4ff',
        'lilac-dark': '#d8b9ff',
        'lilac-darkest': '#d2afff'
      }
    }
  },
  plugins: []
};
