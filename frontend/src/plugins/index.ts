import type { App } from "vue";

import { loadFonts } from "./webfontloader";
import vuetify from "./vuetify";
import router from "./router";

export function registerPlugins(app: App) {
  loadFonts();
  app.use(vuetify).use(router);
}
