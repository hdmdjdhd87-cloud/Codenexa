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
      // ============================================================
      // Typography scale (Design System 2.0, п.4 UI/UX-спецификации).
      // Значения ИЗВЛЕЧЕНЫ из фактического использования по всему
      // фронтенду (grep по text-[Npx] classes), не выдуманы заново —
      // это формализация уже сложившегося визуального языка, не
      // редизайн. Только font-size, БЕЗ line-height: исходные
      // text-[Npx] классы никогда не задавали line-height (наследовали
      // от родителя/браузера) — если бы токены задавали свой
      // line-height, это стало бы реальным визуальным изменением
      // (другой межстрочный интервал), а не чистым переименованием.
      // Заменено на текущих 114 мест по всей кодовой базе (только
      // точные px-совпадения — без консолидации близких значений типа
      // 12px/12.5px, это была бы уже дизайн-декизия, не safe rename).
      //
      // Частота использования (для справки, откуда взялась шкала):
      //   12.5px×48, 12px×40, 13px×28, 13.5px×17, 14px×14, 11.5px×28(≈),
      //   20px×10, 16px×7, 15px×7, 11px×6, 10px×6, 17px×5, 10.5px×5
      fontSize: {
        "cn-2xs": "10px",
        "cn-xs": "11.5px",
        "cn-sm": "12.5px",
        "cn-base": "13.5px",
        "cn-md": "14px",
        "cn-lg": "16px",
        "cn-xl": "17px",
        "cn-2xl": "20px",
        "cn-3xl": "24px",
      },
      // Elevation (shadows) — не было определено вообще, все
      // поверхности различались только border/background. Тени
      // намеренно очень мягкие: тёмная тема по умолчанию, резкая тень
      // выглядела бы чужеродно на #0B0B10.
      boxShadow: {
        "cn-sm": "0 1px 2px rgba(0, 0, 0, 0.16)",
        "cn-md": "0 4px 12px rgba(0, 0, 0, 0.20)",
        "cn-lg": "0 12px 32px rgba(0, 0, 0, 0.28)",
      },
      // Motion tokens (п.14 спецификации: "коротких переходов 150-250ms").
      transitionDuration: {
        "cn-fast": "150ms",
        "cn-base": "200ms",
        "cn-slow": "250ms",
      },
      transitionTimingFunction: {
        "cn-standard": "cubic-bezier(0.2, 0, 0, 1)",
      },
      // z-index scale — раньше только BottomNav имел явный z-40 без
      // задокументированной системы; следующий модальный/sheet-слой
      // рисковал случайно оказаться на том же уровне.
      zIndex: {
        "cn-nav": "40",
        "cn-overlay": "50",
        "cn-modal": "60",
        "cn-toast": "70",
      },
    },
  },
  plugins: [],
};
