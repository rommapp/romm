import mitt from "mitt";
import type { App } from "vue";
import i18n from "@/locales";
import type { Events } from "@/types/emitter";
import { configureMDEditor } from "./mdeditor";
import pinia from "./pinia";
import vuetify from "./vuetify";

export function registerPlugins(app: App) {
  configureMDEditor();
  app.use(vuetify).use(pinia).use(i18n).provide("emitter", mitt<Events>());
}
