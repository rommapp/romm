<script setup lang="ts">
import { ref, inject } from "vue";
import type { Emitter } from "mitt";
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
    :modelValue="show"
    :scrim="false"
    scroll-strategy="none"
    width="auto"
    persistent
  >
    <v-card outlined color="transparent">
      <v-card-text class="pa-4">
        <v-progress-circular
          :width="3"
          :size="70"
          color="romm-accent-1"
          indeterminate
        />
      </v-card-text>
    </v-card>
  </v-dialog>
</template>
