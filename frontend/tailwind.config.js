/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        background: "var(--cn-background)",
        surface: "var(--cn-surface)",
        "surface-elevated": "var(--cn-surface-elevated)",
        border: "var(--cn-border)",
        "text-primary": "var(--cn-text-primary)",
        "text-secondary": "var(--cn-text-secondary)",
        accent: "var(--cn-accent)",
        "accent-secondary": "var(--cn-accent-secondary)",
        success: "var(--cn-success)",
        warning: "var(--cn-warning)",
        error: "var(--cn-error)",
      },
      borderRadius: {
        xl: "18px",
        "2xl": "24px",
      },
      fontFamily: {
        sans: ["-apple-system", "BlinkMacSystemFont", "Inter", "Segoe UI", "sans-serif"],
      },
    },
  },
  plugins: [],
};
