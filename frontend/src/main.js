import { createApp } from "vue";
import { registerPlugins } from "@/plugins";

import App from "./App.vue";

// Event bus
import mitt from "mitt";
const emitter = mitt();

const app = createApp(App);

registerPlugins(app);

app.provide("emitter", emitter);
app.mount("#app");
