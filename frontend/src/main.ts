import { registerPlugins } from "@/plugins";
import "@/styles/fonts.css";
import "@/styles/scrollbar.css";
import type { Events } from "@/types/emitter";
import mitt from "mitt";
import { createApp } from "vue";
import { createVuetify } from "vuetify";
import App from "./App.vue";

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
