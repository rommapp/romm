import "@mdi/font/css/materialdesignicons.css";
import { useLocalStorage } from "@vueuse/core";
import { createVuetify } from "vuetify";
import "vuetify/styles";
import { themes, dark, light, autoThemeKey } from "@/styles/themes";
import { isKeyof } from "@/types";

const mediaMatch = window.matchMedia("(prefers-color-scheme: dark)");
mediaMatch.addEventListener("change", (event) => {
  instance.theme.global.name.value = event.matches ? "dark" : "light";
});

function getTheme() {
  const storedTheme = useLocalStorage("settings.theme", autoThemeKey);

  if (
    storedTheme.value !== autoThemeKey &&
    isKeyof(storedTheme.value, themes)
  ) {
    return themes[storedTheme.value];
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

export default instance;
