/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      // ✅ Merged 'backgroundImage' to include both your gradient and the new one
      backgroundImage: {
        'custom-gradient': 'linear-gradient(to right, rgba(192, 194, 181, 0.67) 0%, rgba(192, 194, 181, 0.67) 21.25%, #6AC277 26.25%, #6AC277 47.5%, #FFC916 52.5%, #FFC916 73.75%, #FF4747 78.75%, #FF4747 100%)',
        'shimmer-gradient': 'linear-gradient(90deg, rgba(255,255,255,0) 0%, rgba(255,255,255,0.4) 50%, rgba(255,255,255,0) 100%)',
        'shimmer-gradient-track': 'linear-gradient(90deg, rgba(0,0,0,0) 0%, rgba(0,0,0,0.04) 50%, rgba(0,0,0,0) 100%)',
      },
      
      // ✨ Added colors, keyframes, and animation for the progress bar
      colors: {
        'mazars-dark-blue': '#003876',
        'mazars-light-blue': '#009cde',
      },
      keyframes: {
        shimmer: {
          '0%': { backgroundPosition: '200% 0' },
          '100%': { backgroundPosition: '-200% 0' },
        },
      },
      animation: {
        shimmer: 'shimmer 2s infinite',
      },
    },
  },
  plugins: [],
}