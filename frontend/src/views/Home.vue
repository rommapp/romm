<script setup lang="ts">
import AppBar from "@/components/AppBar/Base.vue";
import Drawer from "@/components/Drawer/Base.vue";
import platformApi from "@/services/api/platform";
import userApi from "@/services/api/user";
import storeAuth from "@/stores/auth";
import storePlatforms from "@/stores/platforms";
import storeScanning from "@/stores/scanning";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { inject, onMounted, ref } from "vue";
import { useDisplay } from "vuetify";

// Props
const { mdAndDown } = useDisplay();
const scanningStore = storeScanning();
const { scanning } = storeToRefs(scanningStore);
const platformsStore = storePlatforms();
const auth = storeAuth();
const refreshView = ref(0);

// Event listeners bus
const emitter = inject<Emitter<Events>>("emitter");
emitter?.on("refreshDrawer", async () => {
  const { data: platformData } = await platformApi.getPlatforms();
  platformsStore.set(platformData);
});
emitter?.on("refreshView", async () => {
  refreshView.value = refreshView.value + 1;
});

// Functions
onMounted(() => {
  platformApi
    .getPlatforms()
    .then(({ data: platforms }) => {
      platformsStore.set(platforms);
    })
    .catch((error) => {
      console.error(error);
    });

  userApi
    .fetchCurrentUser()
    .then(({ data: user }) => {
      auth.setUser(user);
    })
    .catch((error) => {
      console.error(error);
    });
});
</script>

<template>
  <v-progress-linear
    id="scan-progress-bar"
    color="romm-accent-1"
    :active="scanning"
    :indeterminate="true"
  />
  <drawer />
  <app-bar v-if="mdAndDown" />
  <router-view :key="refreshView" />
</template>

<style scoped>
#scan-progress-bar {
  z-index: 2015 !important;
  position: fixed;
}
</style>
