<script setup lang="ts">
import { inject } from "vue";
import type { Emitter } from "mitt";
import type { Events } from "@/types/emitter";

// Event listeners bus
const emitter = inject<Emitter<Events>>("emitter");
</script>

<template>
  <v-btn @click="emitter?.emit('toggleDrawer')" rounded="0" icon>
    <v-avatar rounded="0">
      <v-img src="/assets/isotipo.svg" />
    </v-avatar>
  </v-btn>
</template>
