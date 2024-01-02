import { createVuetify } from "vuetify";
import { themes, dark, light, autoThemeKey } from "@/styles/themes";

import "vuetify/styles";
import "@mdi/font/css/materialdesignicons.css";

const mediaMatch = window.matchMedia("(prefers-color-scheme: dark)");

function getTheme() {
  const storedTheme = parseInt(localStorage.getItem("settings.theme") ?? "");

  if (
    !isNaN(storedTheme) &&
    storedTheme !== autoThemeKey &&
    isKeyof(storedTheme, themes)
  ) {
    return themes[storedTheme];
  }

  return mediaMatch.matches ? "dark" : "light";
}

const instance = createVuetify({
  icons: {
    defaultSet: "mdi",
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
