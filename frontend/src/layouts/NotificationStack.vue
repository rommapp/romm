<script setup lang="ts">
import Notification from "@/components/common/Notification.vue";
import storeNotifications from "@/stores/notifications";
import type { SnackbarStatus } from "@/types/emitter";
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import type { Events } from "@/types/emitter";
import { inject } from "vue";
const notificationStore = storeNotifications();
const { notifications } = storeToRefs(notificationStore);
const emitter = inject<Emitter<Events>>("emitter");
emitter?.on("snackbarShow", (snackbar: SnackbarStatus) => {
  snackbar.id = notificationStore.notifications.length + 1;
  notificationStore.add(snackbar);
});
</script>
<template>
  <notification
    v-for="notification in notifications"
    :style="{ 'margin-top': `${(notifications.indexOf(notification)+1) * 60}px` }"
  />
</template>
<style scoped></style>
