/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        night: {
          900: "#0f0f14",
          950: "#07070c",
        },
        /* ── Silver / Cream palette (legacy; dark UI uses zinc + night) ── */
        cream: {
          50:  "#FDFCF8",
          100: "#F8F5EE",
          200: "#F0EBE0",
          300: "#E4DDD0",
          400: "#CFC7B8",
        },
        silver: {
          100: "#F0F0F2",
          200: "#E2E2E6",
          300: "#C8C8CE",
          400: "#A8A8B0",
          500: "#86868F",
          600: "#65656E",
          700: "#44444C",
          800: "#2A2A30",
          900: "#16161A",
        },
        accent: {
          /* Steel blue — used for CTAs, links, active states */
          DEFAULT: "#4A6FA5",
          light:   "#6B8DBF",
          dark:    "#2F4E7A",
        },
        danger:  "#C0392B",
        success: "#1A7A4A",
        warning: "#B8860B",
      },
      fontFamily: {
        sans: ["Architype Stedelijk", "Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "monospace"],
      },
      boxShadow: {
        card:    "0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04)",
        "card-hover": "0 4px 12px rgba(0,0,0,0.10), 0 2px 4px rgba(0,0,0,0.06)",
        panel:   "0 2px 8px rgba(0,0,0,0.08)",
        glass:   "0 8px 32px rgba(0,0,0,0.45), inset 0 1px 0 rgba(255,255,255,0.08)",
        "glass-lg": "0 24px 64px rgba(0,0,0,0.55), inset 0 1px 0 rgba(255,255,255,0.1)",
      },
      keyframes: {
        blob: {
          "0%, 100%": { transform: "translate(0, 0) scale(1)" },
          "33%": { transform: "translate(28px, -24px) scale(1.06)" },
          "66%": { transform: "translate(-22px, 18px) scale(0.96)" },
        },
      },
      animation: {
        blob: "blob 22s ease-in-out infinite",
        "blob-slow": "blob 32s ease-in-out infinite",
      },
      borderRadius: {
        DEFAULT: "8px",
        lg: "12px",
        xl: "16px",
      },
    },
  },
  plugins: [],
};
