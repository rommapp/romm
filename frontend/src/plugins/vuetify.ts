import "@mdi/font/css/materialdesignicons.css";
import { createVuetify } from "vuetify";
import { VDateInput } from "vuetify/components/VDateInput";
import "vuetify/styles";
import { useUserLocalStorage } from "@/composables/useUserLocalStorage";
import { dark, light } from "@/styles/themes";

// Initial theme resolution only: runtime theme changes are owned by
// RomM.vue, which keeps Vuetify's name in sync with user preference.
// v2 surfaces don't read from Vuetify's runtime theme; they read tokens
// off `.r-v2-dark` / `.r-v2-light` on <html>.
function getInitialTheme(): "dark" | "light" {
  const storedTheme = useUserLocalStorage("settings.theme", "auto");
  const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;

  if (storedTheme.value === "dark") return "dark";
  if (storedTheme.value === "light") return "light";
  return prefersDark ? "dark" : "light";
}

const instance = createVuetify({
  components: {
    VDateInput,
  },
  icons: {
    defaultSet: "mdi",
  },
  theme: {
    defaultTheme: getInitialTheme(),
    themes: { dark, light },
  },
});

export default instance;
