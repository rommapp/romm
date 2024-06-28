<script setup lang="ts">
import storeAuth from "@/stores/auth";
import storeNavigation from "@/stores/navigation";
import { defaultAvatarPath } from "@/utils";

// Props
const navigationStore = storeNavigation();
const auth = storeAuth();
</script>
<template>
  <v-hover v-slot="{ isHovering, props: hoverProps }">
    <v-avatar
      @click="navigationStore.switchActiveSettingsDrawer"
      class="pointer"
      size="35"
      v-bind="hoverProps"
      :class="{ 'border-romm-accent-1': isHovering }"
    >
      <v-img
        :src="
          auth.user?.avatar_path
            ? `/assets/romm/assets/${auth.user?.avatar_path}?ts=${auth.user?.updated_at}`
            : defaultAvatarPath
        "
      />
    </v-avatar>
  </v-hover>
</template>
