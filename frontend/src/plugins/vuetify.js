import { createVuetify } from "vuetify";
import { themes, dark, light, autoThemeKey } from "@/styles/themes";

import "vuetify/styles";
import "@mdi/font/css/materialdesignicons.css";

const mediaMatch = window.matchMedia("(prefers-color-scheme: dark)");

function getTheme() {
  const storedTheme = parseInt(localStorage.getItem("settings.theme"));

  if (storedTheme && storedTheme !== autoThemeKey) {
    return themes[storedTheme];
  }

  return mediaMatch.matches ? "dark" : "light";
}

const instance = createVuetify({
  icons: {
    iconfont: "mdi",
  },
  theme: {
    defaultTheme: getTheme(),
    themes: {
      dark,
      light,
    },
  },
});

mediaMatch.addEventListener("change", (event) => {
  instance.theme.global.name.value = event.matches ? "dark" : "light";
});

export default instance;
