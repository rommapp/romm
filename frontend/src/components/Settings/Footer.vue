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
        <span class="ml-1">{{ heartbeatStore.value.SYSTEM.VERSION }}</span>
        <v-icon>mdi-circle-small</v-icon><v-icon>mdi-github</v-icon>
        <v-hover v-slot="{ isHovering, props }">
          <span class="ml-1"
            ><a
              :class="{
                'text-primary': isHovering,
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
                'text-primary': isHovering,
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
  pointer-events: none;
}
.desktop {
  margin-left: 60px !important;
  width: calc(100% - 60px) !important;
}
</style>
