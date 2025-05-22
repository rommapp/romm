<script setup lang="ts">
import storeAuth from "@/stores/auth";
import storeNavigation from "@/stores/navigation";
import { defaultAvatarPath } from "@/utils";
import { storeToRefs } from "pinia";
import { useDisplay } from "vuetify";

// Props
const navigationStore = storeNavigation();
const auth = storeAuth();
const { user } = storeToRefs(auth);
const { smAndDown } = useDisplay();
</script>
<template>
  <v-avatar
    @keydown.enter="navigationStore.switchActiveSettingsDrawer"
    @click="navigationStore.switchActiveSettingsDrawer"
    class="pointer"
    :size="smAndDown ? 35 : 40"
    :class="{ active: navigationStore.activeSettingsDrawer }"
  >
    <v-img
      :src="
        user?.avatar_path
          ? `/assets/romm/assets/${user?.avatar_path}?ts=${user?.updated_at}`
          : defaultAvatarPath
      "
    />
  </v-avatar>
</template>
<style scoped>
.v-avatar {
  transition: filter 0.15s ease-in-out;
}
.v-avatar:hover,
.v-avatar.active {
  filter: drop-shadow(0px 0px 2px rgba(var(--v-theme-primary)));
}
</style>
