<script setup lang="ts">
import type { Events } from "@/types/emitter";
import storeNavigation from "@/stores/navigation";
import type { Emitter } from "mitt";
import { inject } from "vue";

const navigationStore = storeNavigation();

const emitter = inject<Emitter<Events>>("emitter");
</script>
<template>
  <v-btn
    icon
    variant="flat"
    rounded="0"
    color="background"
    class="rounded my-1"
    @click="navigationStore.goSearch"
  >
    <v-icon :color="$route.name == 'search' ? 'primary' : ''"
      >mdi-magnify</v-icon
    >
  </v-btn>
</template>
