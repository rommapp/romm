<script setup lang="ts">
import storeNavigation from "@/stores/navigation";
import { storeToRefs } from "pinia";
import { useI18n } from "vue-i18n";

// Props
const { t } = useI18n();
const navigationStore = storeNavigation();
const { activePlatformInfoDrawer } = storeToRefs(navigationStore);
</script>

<template>
  <v-tooltip
    location="bottom"
    class="tooltip"
    transition="fade-transition"
    :text="t('platform.show-platform-settings')"
    open-delay="1000"
  >
    <template #activator="{ props }">
      <v-btn
        variant="text"
        rounded="0"
        v-bind="props"
        icon="mdi-cog"
        :color="activePlatformInfoDrawer ? 'primary' : ''"
        aria-label="Platform settings"
        @click="navigationStore.switchActivePlatformInfoDrawer()"
      />
    </template>
  </v-tooltip>
</template>
