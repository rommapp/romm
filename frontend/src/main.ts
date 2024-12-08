import { registerPlugins } from "@/plugins";
import "@/styles/common.css";
import "@/styles/fonts.css";
import "@/styles/scrollbar.css";
import type { Events } from "@/types/emitter";
import mitt from "mitt";
import { createApp } from "vue";
import App from "@/RomM.vue";

const emitter = mitt<Events>();
const app = createApp(App);
registerPlugins(app);
app.provide("emitter", emitter);
app.mount("#app");
