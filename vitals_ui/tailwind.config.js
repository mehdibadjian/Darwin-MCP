/** @type {import("tailwindcss").Config} */
module.exports = {
  darkMode: "class",
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        sovereign: {
          bg:     "#0a0a0a",
          panel:  "#111111",
          border: "#1a1a1a",
          accent: "#00ff41",
          muted:  "#4a4a4a",
          text:   "#e0e0e0",
        },
      },
      fontFamily: {
        mono: ["JetBrains Mono", "Fira Code", "Consolas", "monospace"],
      },
    },
  },
  plugins: [],
};
