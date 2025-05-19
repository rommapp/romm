<script setup lang="ts">
import storeNotifications from "@/stores/notifications";
import type { Events, SnackbarStatus } from "@/types/emitter";
import type { Emitter } from "mitt";
import { inject, ref } from "vue";
import { useDisplay } from "vuetify";

// Props
const show = ref(false);
const { xs } = useDisplay();
const snackbarStatus = ref<SnackbarStatus>({ msg: "" });
const notificationStore = storeNotifications();

// Event listeners bus
const emitter = inject<Emitter<Events>>("emitter");
emitter?.on("snackbarShow", (snackbar: SnackbarStatus) => {
  show.value = true;
  snackbarStatus.value = snackbar;
  snackbarStatus.value.id = notificationStore.notifications.length + 1;
});

function closeDialog() {
  notificationStore.remove(snackbarStatus.value.id);
  show.value = false;
}
</script>

<template>
  <v-snackbar
    transition="scroll-y-transition"
    v-model="show"
    :timeout="snackbarStatus.timeout || 3000"
    @timeout="closeDialog"
    absolute
    :location="xs ? 'top' : 'top right'"
    color="primary-darken"
  >
    <template #text>
      <v-row class="d-flex align-start flex-row flex-nowrap px-2">
        <v-icon :icon="snackbarStatus.icon" class="mx-2 mt-1" />
        <span class="text-subtitle-1 font-weight-regular">
          {{ snackbarStatus.msg }}
        </span>
      </v-row>
    </template>
    <template #actions>
      <v-btn variant="text" @click="closeDialog">
        <v-icon icon="mdi-close" />
      </v-btn>
    </template>
  </v-snackbar>
</template>
