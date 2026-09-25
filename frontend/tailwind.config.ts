import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ["var(--font-sans)", "ui-sans-serif", "system-ui", "sans-serif"],
        display: ["var(--font-display)", "Georgia", "serif"],
      },
      colors: {
        border: "hsl(var(--border))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        success: "hsl(var(--success))",
        warning: "hsl(var(--warning))",
        ink: {
          DEFAULT: "hsl(var(--ink))",
          2: "hsl(var(--ink-2))",
        },
        cream: {
          50: "hsl(var(--cream-50))",
          100: "hsl(var(--cream-100))",
          200: "hsl(var(--cream-200))",
        },
        sage: {
          100: "hsl(var(--sage-100))",
          200: "hsl(var(--sage-200))",
          300: "hsl(var(--sage-300))",
          400: "hsl(var(--sage-400))",
          500: "hsl(var(--sage-500))",
          600: "hsl(var(--sage-600))",
          700: "hsl(var(--sage-700))",
        },
        blush: {
          100: "hsl(var(--blush-100))",
          200: "hsl(var(--blush-200))",
          500: "hsl(var(--blush-500))",
        },
        slate: {
          500: "hsl(var(--slate-500))",
        },
        /* Legacy alias: pages written against the old sky-* scale now resolve
           to the sage ramp instead of Tailwind's default blue. */
        sky: {
          50: "hsl(var(--sky-50))",
          100: "hsl(var(--sky-100))",
          200: "hsl(var(--sky-200))",
          300: "hsl(var(--sky-300))",
          400: "hsl(var(--sky-400))",
          500: "hsl(var(--sky-500))",
          600: "hsl(var(--sky-600))",
          700: "hsl(var(--sky-700))",
          900: "hsl(var(--sky-900))",
        },
      },
      borderRadius: {
        /* Sharp, structured UI: no rounded cards/buttons/pills. A hair of
           radius is kept only for `lg`/`xl` so focus rings and hairline
           borders don't look aliased; everything else is a true square edge. */
        none: "0px",
        sm: "0px",
        DEFAULT: "0px",
        md: "0px",
        lg: "var(--radius)",
        xl: "calc(var(--radius) + 1px)",
        full: "9999px",
      },
      animation: {
        marquee: "mv-marquee 34s linear infinite",
        drift: "mv-drift 7s ease-in-out infinite",
        scene: "mv-scene 1.5s cubic-bezier(0.16, 1, 0.3, 1) both",
        "pulse-soft": "mv-pulse 2s ease-in-out infinite",
        breathe: "mv-breathe 11s ease-in-out infinite",
        draw: "mv-draw 2s cubic-bezier(0.16, 1, 0.3, 1) both",
      },
      transitionTimingFunction: {
        editorial: "cubic-bezier(0.16, 1, 0.3, 1)",
      },
    },
  },
  plugins: [],
};

export default config;
