<script setup lang="ts">
// TryV2Banner — bottom-center sticky card shown in v1 to nudge users
// toward the v2 UI. Mirrors NewVersionDialog's visual rhythm so the
// two banners read as siblings when both are visible (NewVersionDialog
// sits above this one because it mounts later in Main.vue).
//
// Dismissal persists in localStorage; clicking "Switch now" flips the
// shared `useUiVersion` ref to "v2" (the page re-renders into the v2
// layout immediately because RomM.vue watches the same ref).
//
// Lives in v1 deliberately — v1 is otherwise frozen, but a single
// promotional banner pointing users at the new UI directly supports
// the migration goal documented in CLAUDE.md.
import { useLocalStorage } from "@vueuse/core";
import { ref } from "vue";
import { useUiVersion } from "@/composables/useUiVersion";

const uiVersion = useUiVersion();
const dismissed = useLocalStorage("ui.dismissedTryV2", false);
// Local close affordance so the banner animates out before the
// persisted flag is read on the next mount.
const visible = ref(!dismissed.value);

function dismissBanner() {
  dismissed.value = true;
  visible.value = false;
}

function switchToV2() {
  dismissed.value = true;
  visible.value = false;
  uiVersion.value = "v2";
}
</script>

<template>
  <div v-if="visible" class="pa-3 sticky-bottom">
    <v-slide-y-transition>
      <v-card
        v-if="visible"
        class="pa-1 border-selected mx-auto"
        max-width="fit-content"
      >
        <v-card-text class="text-center py-2 px-4">
          <v-icon
            icon="mdi-creation"
            size="small"
            color="primary"
            class="mr-1"
          />
          <span class="text-body-1">Try the new UI</span>
          <span class="text-primary ml-2 text-body-1 font-weight-medium">
            Beta
          </span>
          <v-row class="mt-2 flex justify-center" no-gutters>
            <v-btn-group>
              <v-btn
                density="compact"
                variant="outlined"
                class="pointer"
                size="small"
                @click="dismissBanner"
              >
                Dismiss
              </v-btn>
              <v-btn
                density="compact"
                variant="tonal"
                color="primary"
                size="small"
                @click="switchToV2"
              >
                Switch now
              </v-btn>
            </v-btn-group>
          </v-row>
        </v-card-text>
      </v-card>
    </v-slide-y-transition>
  </div>
</template>

<style scoped>
.sticky-bottom {
  position: fixed;
  bottom: 0;
  left: 0;
  width: 100%;
  z-index: 9998;
  pointer-events: none;
}
.sticky-bottom * {
  pointer-events: auto;
}
</style>
