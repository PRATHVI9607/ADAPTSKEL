export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        'space-black': '#0a0a0f',
        'deep-navy': '#0d1117',
        'skeleton-blue': '#00d4ff',
        'heat-amber': '#ff8c00',
        'path-gold': '#ffd700',
        'insert-green': '#00ff88',
        'delete-red': '#ff4444',
      },
      fontFamily: {
        display: ['Space Grotesk', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
        body: ['Inter', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
