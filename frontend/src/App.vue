<script setup lang="ts">
import Notification from "@/components/common/Notification.vue";
import api from "@/services/api/index";
import storeConfig from "@/stores/config";
import storeHeartbeat from "@/stores/heartbeat";
import storeNotifications from "@/stores/notifications";
import { storeToRefs } from "pinia";
import { onMounted } from "vue";

// Props
const notificationStore = storeNotifications();
const { notifications } = storeToRefs(notificationStore);
const heartbeat = storeHeartbeat();
const configStore = storeConfig();

onMounted(async () => {
  await api.get("/heartbeat").then(({ data: data }) => {
    heartbeat.set(data);
  });

  await api.get("/config").then(({ data: data }) => {
    configStore.set(data);
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
