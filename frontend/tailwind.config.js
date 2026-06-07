/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          bg: "#F4F1EA",
          muted: "#9B8A78",
          gold: "#F4C84A",
          "gold-muted": "#F7D76A",
          surface: {
            DEFAULT: "#FFFFFF",
            bg: "#F4F1EA",
            muted: "#F7F4EE",
            warm: "#FFFDFB",
            alt: "#FFF8F2",
            cream: "#FFF6EC",
            pink: "#F1E7DA",
            yellow: "#FFF7D6",
            yellowLight: "#FFF5E3",
            yellowBadge: "#FFF8E8",
          },
          text: {
            DEFAULT: "#1A1A1A",
            muted: "#666666",
            section: "#FF5C00",
            workflow: "#7A6B60",
            goldBadge: "#3B2F12",
            goldDark: "#2F250E",
            step: "#1A1A1A",
          },
          border: {
            DEFAULT: "#E8DED0",
            warm: "#F1E6D8",
            form: "#F1DDD0",
            pink: "#FFDCC7",
            pinkLight: "#FFE5D3",
            card: "#F1DDD0",
            upload: "#D8C9B8",
            tool: "#F3E0D2",
            gold: "#E9C95E",
            goldLight: "#DBB64D",
            yellowStrong: "#D8AF39",
          },
        },
      },
      fontFamily: {
        sans: ["Geist", "sans-serif"],
        serif: ["Newsreader", "serif"],
        caption: ["Funnel Sans", "sans-serif"],
      },
    },
  },
  plugins: [],
};
