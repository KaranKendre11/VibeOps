/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        bg: '#000000',
        // Cosmic crimson-black surfaces — a faint magenta cast reads as deep nebula
        // space rather than a neutral dark UI panel.
        surface: '#140610',
        'surface-2': '#26101c',
        fg: '#ffffff',
        // Pink-tinted greys so muted text sits in the same magenta key as the field.
        'fg-muted': '#ded0d6',
        'fg-dim': '#a68a99',
        line: 'rgba(255,190,214,0.16)',
        accent: '#ff4d8d',
        'accent-dim': 'rgba(255,77,141,0.55)',
        // Magenta nebula accent + a deeper crimson tone for the ambient background glows.
        nebula: '#ff4d8d',
        'nebula-deep': '#8f1d4a',
      },
      fontFamily: {
        // Body / UI.
        sans: ['"Space Grotesk"', 'system-ui', 'sans-serif'],
        // The machine: code, logs, telemetry readouts + tracked-out micro-labels.
        mono: ['"JetBrains Mono"', 'ui-monospace', 'SFMono-Regular', 'monospace'],
      },
      transitionTimingFunction: {
        // Signature easing — easeOutQuint. Restrained, precise, never springy.
        quint: 'cubic-bezier(0.23, 1, 0.32, 1)',
      },
      borderRadius: {
        sm: '8px',
        md: '16px',
        lg: '25px',
        pill: '100px',
      },
      boxShadow: {
        glow: '0 0 20px rgba(255,77,141,0.5)',
        'glow-sm': '0 0 12px rgba(255,77,141,0.35)',
        'glow-lg': '0 0 44px rgba(255,77,141,0.45)',
        'glow-inset': 'inset 0 0 20px rgba(255,77,141,0.08)',
        // Liquid-glass elevation tiers: outer depth + top-edge highlight.
        'glass-1': '0 4px 20px rgba(0,0,0,0.35), inset 0 1px 0 rgba(255,255,255,0.08)',
        'glass-2': '0 16px 40px rgba(0,0,0,0.45), inset 0 1px 0 rgba(255,255,255,0.10)',
        'glass-3': '0 30px 70px rgba(0,0,0,0.55), inset 0 1px 0 rgba(255,255,255,0.14)',
      },
      keyframes: {
        marquee: {
          '0%': { transform: 'translateX(0)' },
          '100%': { transform: 'translateX(-50%)' },
        },
        breathe: {
          '0%, 100%': {
            opacity: '0.75',
            filter: 'drop-shadow(0 0 10px rgba(255,77,141,0.45))',
          },
          '50%': {
            opacity: '1',
            filter: 'drop-shadow(0 0 30px rgba(255,77,141,0.85))',
          },
        },
        blob: {
          '0%, 100%': { transform: 'translate(0px, 0px) scale(1)' },
          '33%': { transform: 'translate(30px, -40px) scale(1.08)' },
          '66%': { transform: 'translate(-24px, 26px) scale(0.94)' },
        },
        blink: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0' },
        },
        'fade-up': {
          '0%': { opacity: '0', transform: 'translateY(8px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        // Slow, GPU-cheap aurora drift — the "cloud" substrate. Multi-step,
        // desynced paths with gentle opacity breathing so the field feels alive
        // rather than sliding back and forth. Frozen under prefers-reduced-motion.
        'aurora-a': {
          '0%, 100%': { transform: 'translate(0, 0) scale(1)', opacity: '0.85' },
          '25%': { transform: 'translate(5%, 4%) scale(1.1)', opacity: '1' },
          '50%': { transform: 'translate(9%, 8%) scale(1.16)', opacity: '0.75' },
          '75%': { transform: 'translate(4%, 3%) scale(1.06)', opacity: '0.95' },
        },
        'aurora-b': {
          '0%, 100%': { transform: 'translate(0, 0) scale(1)', opacity: '0.8' },
          '25%': { transform: 'translate(-6%, 5%) scale(1.08)', opacity: '0.95' },
          '50%': { transform: 'translate(-9%, 9%) scale(1.14)', opacity: '0.68' },
          '75%': { transform: 'translate(-3%, 4%) scale(1.05)', opacity: '0.9' },
        },
        'aurora-c': {
          '0%, 100%': { transform: 'translate(0, 0) scale(1)', opacity: '0.7' },
          '33%': { transform: 'translate(6%, -6%) scale(1.12)', opacity: '0.9' },
          '66%': { transform: 'translate(-5%, -3%) scale(0.96)', opacity: '0.8' },
        },
        'aurora-d': {
          '0%, 100%': { transform: 'translate(0, 0) scale(1)', opacity: '0.6' },
          '50%': { transform: 'translate(-7%, -7%) scale(1.13)', opacity: '0.82' },
        },
        'pulse-glow': {
          '0%, 100%': { opacity: '0.5' },
          '50%': { opacity: '1' },
        },
      },
      animation: {
        marquee: 'marquee 26s linear infinite',
        breathe: 'breathe 4.5s ease-in-out infinite',
        blink: 'blink 1.1s step-end infinite',
        'fade-up': 'fade-up 0.4s ease-out both',
        'aurora-a': 'aurora-a 42s ease-in-out infinite',
        'aurora-b': 'aurora-b 52s ease-in-out infinite',
        'aurora-c': 'aurora-c 60s ease-in-out infinite',
        'aurora-d': 'aurora-d 48s ease-in-out infinite',
        'pulse-glow': 'pulse-glow 1.6s ease-in-out infinite',
      },
    },
  },
  plugins: [],
};
