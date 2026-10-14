// Mirrors the Maehai Design System tokens (light values; dark via CSS variables in packages/ui/src/tokens.css).
module.exports = {
  theme: {
    extend: {
      colors: {
        surface: { 100: "var(--surface-100)", 200: "var(--surface-200)", 300: "var(--surface-300)" },
        ink: { DEFAULT: "var(--ink)", muted: "var(--ink-muted)" },
        line: { DEFAULT: "var(--line)", strong: "var(--line-strong)" },
        leaf: { DEFAULT: "var(--leaf)", hover: "var(--leaf-hover)", on: "var(--on-leaf)", soft: "var(--leaf-soft)" },
        band: { yellow: "var(--band-yellow)", red: "var(--band-red)", green: "var(--band-green)" },
        success: "var(--success)", warning: "var(--warning)", info: "var(--info)", danger: "var(--danger)",
      },
      fontFamily: {
        display: ["Mitr", "IBM Plex Sans Thai", "system-ui", "sans-serif"],
        sans: ["IBM Plex Sans Thai", "Noto Sans Thai", "system-ui", "sans-serif"],
        mono: ["IBM Plex Mono", "ui-monospace", "monospace"],
      },
      borderRadius: { sm: "8px", md: "12px", lg: "20px", pill: "999px" },
    },
  },
};
