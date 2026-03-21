import "@mdi/font/css/materialdesignicons.css";
import { useLocalStorage } from "@vueuse/core";
import { createVuetify } from "vuetify";
import { VDateInput } from "vuetify/labs/VDateInput";
import "vuetify/styles";
import { dark, light } from "@/styles/themes";

const mediaMatch = window.matchMedia("(prefers-color-scheme: dark)");
mediaMatch.addEventListener("change", (event) => {
  instance.theme.change(event.matches ? "dark" : "light");
});

function getTheme() {
  const storedTheme = useLocalStorage("settings.theme", "auto");

  if (storedTheme.value === "dark" || storedTheme.value === "light") {
    return storedTheme.value;
  }

  return mediaMatch.matches ? "dark" : "light";
}

const instance = createVuetify({
  components: {
    VDateInput,
  },
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
