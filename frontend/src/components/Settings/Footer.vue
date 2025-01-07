<script setup lang="ts">
import storeHeartbeat from "@/stores/heartbeat";
import { useI18n } from "vue-i18n";

// Props
const { t } = useI18n();
const heartbeatStore = storeHeartbeat();
</script>
<template>
  <v-bottom-navigation
    :elevation="0"
    height="36"
    class="bg-terciary text-caption"
  >
    <v-row class="align-center justify-center" no-gutters>
      <span class="text-romm-accent-1">RomM</span>
      <span class="ml-1">{{ heartbeatStore.value.SYSTEM.VERSION }}</span>
      <v-icon>mdi-circle-small</v-icon><v-icon>mdi-github</v-icon>
      <v-hover v-slot="{ isHovering, props }">
        <span class="ml-1"
          ><a
            :class="{
              'text-romm-accent-1': isHovering,
              'text-white': !isHovering,
            }"
            v-bind="props"
            style="text-decoration: none"
            href="https://github.com/rommapp/romm"
            target="_blank"
            >Github</a
          ></span
        >
      </v-hover>
      <v-icon>mdi-circle-small</v-icon>
      <v-hover v-slot="{ isHovering, props }">
        <span class="ml-1"
          ><a
            :class="{
              'text-romm-accent-1': isHovering,
              'text-white': !isHovering,
            }"
            v-bind="props"
            style="text-decoration: none"
            href="https://discord.com/invite/P5HtHnhUDH"
            target="_blank"
            >{{ t("settings.join-discord") }}</a
          ></span
        >
      </v-hover>
    </v-row>
  </v-bottom-navigation>
</template>
