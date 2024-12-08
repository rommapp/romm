import { registerPlugins } from "@/plugins";
import "@/styles/common.css";
import "@/styles/fonts.css";
import "@/styles/scrollbar.css";
import type { Events } from "@/types/emitter";
import mitt from "mitt";
import { createI18n } from "vue-i18n";
import en_US from "@/locales/en_US.json";
import en_GB from "@/locales/en_GB.json";
import es_ES from "@/locales/es_ES.json";
import fr_FR from "@/locales/fr_FR.json";
import ru_RU from "@/locales/ru_RU.json";
import { createApp } from "vue";
import App from "@/RomM.vue";

// Create i18n instance
const i18n = createI18n({
  legacy: false, // Enable Composition API mode
  locale: "en_US", // Default language
  fallbackLocale: "en_US",
  messages: { en_US, en_GB, es_ES, fr_FR, ru_RU },
});

const emitter = mitt<Events>();
const app = createApp(App);
registerPlugins(app);
app.provide("emitter", emitter);
app.use(i18n);
app.mount("#app");
