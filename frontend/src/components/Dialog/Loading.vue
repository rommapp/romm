<script setup>
import { ref, inject } from "vue";

const show = ref(false);
const scrim = ref(false);

const emitter = inject("emitter");
emitter.on("showLoadingDialog", (args) => {
  show.value = args.loading;
  scrim.value = args.scrim;
});
</script>

<template>
  <v-dialog
    :modelValue="show"
    :scrim="false"
    scroll-strategy="none"
    width="auto"
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
