<script setup>
import { ref, inject } from "vue";

// Props
const snackbarShow = ref(false);
const snackbarStatus = ref({});

// Event listeners bus
const emitter = inject("emitter");
emitter.on("snackbarShow", (snackbar) => {
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
        <v-icon icon="mdi-close"/>
      </v-btn>
    </template>
  </v-snackbar>
</template>
