<script setup lang="ts">
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { inject, ref } from "vue";

const show = ref(false);
const scrim = ref(false);
const emitter = inject<Emitter<Events>>("emitter");
emitter?.on("showLoadingDialog", (args) => {
  show.value = args.loading;
  scrim.value = args.scrim;
});
</script>

<template>
  <v-dialog :model-value="show" scroll-strategy="none" width="auto" persistent>
    <v-progress-circular :width="3" :size="70" color="primary" indeterminate />
  </v-dialog>
</template>
