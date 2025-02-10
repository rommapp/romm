import i18n from "@/locales";
import type { Events } from "@/types/emitter";
import mitt from "mitt";
import type { App } from "vue";
import vuetify from "./vuetify";
import pinia from "./pinia";
import { configureMDEditor } from "./mdeditor";

export function registerPlugins(app: App) {
  configureMDEditor();
  app.use(vuetify).use(pinia).use(i18n).provide("emitter", mitt<Events>());
}
