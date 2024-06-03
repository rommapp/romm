<script setup lang="ts">
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { inject } from "vue";

// Event listeners bus
const emitter = inject<Emitter<Events>>("emitter");
</script>

<template>
  <v-app-bar elevation="1" density="comfortable">
    <v-btn
      class="ml-5"
      rounded="0"
      icon
      @click="emitter?.emit('toggleDrawer', null)"
    >
      <v-avatar rounded="0">
        <img src="/assets/isotipo.svg" />
      </v-avatar>
    </v-btn>
  </v-app-bar>
</template>
