<script setup>
import { ref, inject } from "vue";

const show = ref(false);
const scrim = ref(false);

const emitter = inject("emitter");
emitter.on("showLoadingDialog", (loading, setScrim) => {
  show.value = loading;
  scrim.value = setScrim;
});
</script>

<template>
  <v-dialog
    :modelValue="show"
    scroll-strategy="none"
    width="auto"
    :scrim="false"
    persistent
  >
    <v-progress-circular
      :width="3"
      :size="70"
      color="rommAccent1"
      indeterminate
    />
  </v-dialog>
</template>
