import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // Tema oscuro estilo Bloomberg
        bg: {
          DEFAULT: "#0a0a0a",
          card: "#141414",
          hover: "#1a1a1a",
          border: "#262626",
        },
        accent: {
          DEFAULT: "#00d4aa",
          hover: "#00b894",
        },
        danger: "#ef4444",
        warning: "#f59e0b",
        success: "#22c55e",
      },
      fontFamily: {
        mono: ["JetBrains Mono", "monospace"],
      },
    },
  },
  plugins: [],
};

export default config;

