import { registerPlugins } from "@/plugins";
import "@/styles/fonts.css";
import "@/styles/scrollbar.css";
import { createApp } from "vue";
import { createVuetify } from "vuetify";
import App from "./App.vue";

export default createVuetify({
  defaults: {
    VBtn: {
      rounded: 0, // TODO: Vuetify global configuration not working
    },
  },
});

const app = createApp(App);

registerPlugins(app);

app.mount("#app");
