<script setup lang="ts">
import { ref, inject } from "vue";
import type { Emitter } from "mitt";
import type { SnackbarStatus, Events } from "@/types/emitter";

// Props
const snackbarShow = ref(false);
const snackbarStatus = ref<SnackbarStatus>({ msg: "" });

// Event listeners bus
const emitter = inject<Emitter<Events>>("emitter");
emitter?.on("snackbarShow", (snackbar: SnackbarStatus) => {
  snackbarShow.value = true;
  snackbarStatus.value = snackbar;
});
</script>

<template>
  <v-snackbar
    v-model="snackbarShow"
    :timeout="snackbarStatus.timeout ? snackbarStatus.timeout : 2000"
    location="top"
    color="tooltip"
  >
    <v-icon
      :icon="snackbarStatus.icon"
      :color="snackbarStatus.color"
      class="mx-2"
    />
    {{ snackbarStatus.msg }}
    <template v-slot:actions>
      <v-btn @click="snackbarShow = false" variant="text">
        <v-icon icon="mdi-close" />
      </v-btn>
    </template>
  </v-snackbar>
</template>
