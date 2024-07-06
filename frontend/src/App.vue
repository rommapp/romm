<script setup lang="ts">
import Notification from "@/components/common/Notification.vue";
import api from "@/services/api/index";
import userApi from "@/services/api/user";
import storeAuth from "@/stores/auth";
import storeConfig from "@/stores/config";
import storeHeartbeat from "@/stores/heartbeat";
import storeNotifications from "@/stores/notifications";
import Cookies from "js-cookie";
import { storeToRefs } from "pinia";
import { onBeforeMount } from "vue";
import router from "./plugins/router";

// Props
const notificationStore = storeNotifications();
const { notifications } = storeToRefs(notificationStore);
const heartbeat = storeHeartbeat();
const auth = storeAuth();
const configStore = storeConfig();

onBeforeMount(async () => {
  await api
    .get("/heartbeat")
    .then(async ({ data: data }) => {
      heartbeat.set(data);
      if (heartbeat.value.SHOW_SETUP_WIZARD) {
        router.push({ name: "setup" });
      } else {
        await userApi
          .fetchCurrentUser()
          .then(({ data: user }) => {
            auth.setUser(user);
          })
          .catch((error) => {
            console.error(error);
          });

        await api.get("/config").then(({ data: data }) => {
          configStore.set(data);
        });
      }
    })
    .catch(() => {
      const allCookies = Cookies.get(); // Get all cookies
      for (let cookie in allCookies) {
        Cookies.remove(cookie); // Remove each cookie
      }
      router.push({
        name: "login",
      });
    });
});
</script>

<template>
  <v-app>
    <v-main>
      <notification />
      <!-- <notification-stack /> -->
      <router-view />
    </v-main>
  </v-app>
</template>
