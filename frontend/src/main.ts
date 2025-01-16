import App from "@/RomM.vue";
import { registerPlugins } from "@/plugins";
import router from "@/plugins/router";
import api from "@/services/api/index";
import userApi from "@/services/api/user";
import storeAuth from "@/stores/auth";
import storeConfig from "@/stores/config";
import storeHeartbeat from "@/stores/heartbeat";
import "@/styles/common.css";
import "@/styles/fonts.css";
import "@/styles/scrollbar.css";
import { createApp } from "vue";

async function initializeData() {
  const heartbeat = storeHeartbeat();
  const auth = storeAuth();
  const configStore = storeConfig();

  // Load initial data (config + heartbeat + user)
  try {
    const { data: heartbeatData } = await api.get("/heartbeat");
    heartbeat.set(heartbeatData);

    try {
      const { data: userData } = await userApi.fetchCurrentUser();
      auth.setUser(userData);
    } catch (userError) {
      console.error("Error loading user: ", userError);
    }

    const { data: configData } = await api.get("/config");
    configStore.set(configData);
  } catch (error) {
    console.error("Error during initialization: ", error);
  }
}

async function initializeApp() {
  const app = createApp(App);

  // Registrar vuetify + pinia + i18n + emitter
  registerPlugins(app);

  await initializeData();

  app.use(router);

  app.mount("#app");
}

initializeApp();
