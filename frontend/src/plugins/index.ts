import mitt from "mitt";
import type { App } from "vue";
import i18n from "@/locales";
import type { Events } from "@/types/emitter";
import pinia from "./pinia";

export function registerPlugins(app: App) {
  app.use(pinia).use(i18n).provide("emitter", mitt<Events>());
}
