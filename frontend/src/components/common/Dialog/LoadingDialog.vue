<script setup lang="ts">
import type { Emitter } from "mitt";
import { ref, inject } from "vue";
import type { Events } from "@/types/emitter";

const show = ref(false);
const scrim = ref(false);

const emitter = inject<Emitter<Events>>("emitter");
emitter?.on("showLoadingDialog", (args) => {
  show.value = args.loading;
  scrim.value = args.scrim;
});
</script>

<template>
  <v-dialog
    :model-value="show"
    :scrim="scrim"
    scroll-strategy="none"
    width="auto"
    persistent
  >
    <v-progress-circular
      :width="3"
      :size="70"
      color="romm-accent-1"
      indeterminate
    />
  </v-dialog>
</template>
