import { createApp } from "vue";
import { createVuetify } from "vuetify";
import mitt from "mitt";

import { registerPlugins } from "@/plugins";
import App from "./App.vue";
import type { Events } from "@/types/emitter";

const emitter = mitt<Events>();

export default createVuetify({
  defaults: {
    VBtn: {
      rounded: 0, // TODO: Vuetify global configuration not working
    },
  },
});

const app = createApp(App);

registerPlugins(app);

app.provide("emitter", emitter);
app.mount("#app");
