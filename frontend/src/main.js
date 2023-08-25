import { createApp } from "vue";
import { createVuetify } from "vuetify";
import { registerPlugins } from "@/plugins";
import App from "./App.vue";

// Event bus
import mitt from "mitt";
const emitter = mitt();

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
