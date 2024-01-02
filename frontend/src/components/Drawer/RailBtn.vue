<script setup lang="ts">
import { inject } from "vue";
import type { Emitter } from "mitt";
import type { Events } from "@/types/emitter";

// Props
const props = defineProps(["rail"]);

// Event listeners bus
const emitter = inject<Emitter<Events>>("emitter");
</script>

<template>
  <v-btn
    @click="emitter?.emit('toggleDrawerRail')"
    color="primary"
    elevation="0"
    block
  >
    <v-icon v-if="rail">mdi-arrow-collapse-right</v-icon>
    <v-icon v-if="!rail">mdi-arrow-collapse-left</v-icon>
  </v-btn>
</template>
