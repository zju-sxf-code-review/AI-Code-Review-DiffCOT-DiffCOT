/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Replicating system colors roughly
        'window-bg': '#F5F5F5', // Light mode window background
        'sidebar-bg': '#F0F0F0', // Light mode sidebar
      }
    },
  },
  plugins: [],
}
