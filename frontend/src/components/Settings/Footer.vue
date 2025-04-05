<script setup lang="ts">
import storeHeartbeat from "@/stores/heartbeat";
import { useI18n } from "vue-i18n";
import { useDisplay } from "vuetify";

// Props
const { t } = useI18n();
const { smAndDown } = useDisplay();
const heartbeatStore = storeHeartbeat();
</script>
<template>
  <div :class="{ desktop: !smAndDown }" class="sticky-bottom">
    <v-card class="bg-toplayer ma-2 pa-2">
      <v-row class="align-center justify-center" no-gutters>
        <v-hover v-slot="{ isHovering, props }">
          <a
            :href="`https://github.com/rommapp/romm/releases/tag/${heartbeatStore.value.SYSTEM.VERSION}`"
            target="_blank"
            rel="noopener noreferrer"
            class="text-decoration-none text-body-2"
            v-bind="props"
            :class="{
              'text-secondary': isHovering,
            }"
          >
            <code class="px-2 py-1 rounded-sm bg-surface text-primary">
              {{ heartbeatStore.value.SYSTEM.VERSION }}
            </code>
          </a>
        </v-hover>
        <v-icon>mdi-circle-small</v-icon>
        <v-hover v-slot="{ isHovering, props }">
          <a
            href="https://github.com/rommapp/romm"
            target="_blank"
            rel="noopener noreferrer"
            class="text-decoration-none text-primary"
            v-bind="props"
            :class="{
              'text-secondary': isHovering,
            }"
            >Github</a
          >
        </v-hover>
        <v-icon>mdi-circle-small</v-icon>
        <v-hover v-slot="{ isHovering, props }">
          <a
            href="https://discord.com/invite/P5HtHnhUDH"
            target="_blank"
            rel="noopener noreferrer"
            class="text-decoration-none text-primary"
            v-bind="props"
            :class="{
              'text-secondary': isHovering,
            }"
            >Discord</a
          >
        </v-hover>
      </v-row>
    </v-card>
  </div>
</template>
<style scoped>
.sticky-bottom {
  position: fixed;
  bottom: 0;
  left: 0;
  z-index: 1000;
  width: 100%;
}
.desktop {
  margin-left: 60px !important;
  width: calc(100% - 60px) !important;
}
</style>
