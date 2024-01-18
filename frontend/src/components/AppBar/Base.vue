<script setup lang="ts">
import DrawerToggle from "@/components/AppBar/DrawerToggle.vue";
import storeScanning from "@/stores/scanning";
import { storeToRefs } from "pinia";

// Props
const scanningStore = storeScanning();
const { scanning } = storeToRefs(scanningStore);
</script>

<template>
  <v-app-bar elevation="1" density="comfortable">
    <v-progress-linear
      color="romm-accent-1"
      :active="scanning"
      :indeterminate="true"
      absolute
    />
    <drawer-toggle class="ml-5" />
  </v-app-bar>
</template>
