import i18n from "@/locales";
import type { Events } from "@/types/emitter";
import mitt from "mitt";
import type { App } from "vue";
import vuetify from "./vuetify";
import { loadFonts } from "./webfontloader";
import pinia from "./pinia";

export function registerPlugins(app: App) {
  loadFonts();
  app.use(vuetify).use(pinia).use(i18n).provide("emitter", mitt<Events>());
}
