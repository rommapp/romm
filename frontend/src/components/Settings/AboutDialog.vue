<script setup lang="ts">
import storeHeartbeat from "@/stores/heartbeat";
import RDialog from "@/components/common/RDialog.vue";
import RIsotipo from "@/components/common/RIsotipo.vue";
import { ref, inject } from "vue";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { useI18n } from "vue-i18n";

// Props
const { t } = useI18n();
const heartbeatStore = storeHeartbeat();
const emitter = inject<Emitter<Events>>("emitter");
const show = ref(false);
emitter?.on("showAboutDialog", () => {
  show.value = true;
});

// Functions
function closeDialog() {
  show.value = false;
}
</script>
<template>
  <r-dialog
    @close="closeDialog"
    v-model="show"
    icon="mdi-help-circle-outline"
    scroll-content
    width="550px"
  >
    <template #content>
      <v-row class="align-center pa-4" no-gutters>
        <v-col class="pa-4" cols="6">
          <r-isotipo class="mr-2 mb-1" :size="20" /><span>RomM version</span>
          <v-divider class="my-2" />
          <v-hover v-slot="{ isHovering, props }">
            <a
              :href="`https://github.com/rommapp/romm/releases/tag/${heartbeatStore.value.SYSTEM.VERSION}`"
              target="_blank"
              rel="noopener noreferrer"
              class="text-decoration-none text-primary"
              v-bind="props"
              :class="{
                'text-secondary': isHovering,
              }"
            >
              {{ heartbeatStore.value.SYSTEM.VERSION }}
            </a>
          </v-hover>
        </v-col>
        <v-col class="pa-4" cols="6">
          <v-icon class="mr-2">mdi-code-braces</v-icon><span>Source code</span>
          <v-divider class="my-2" />
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
        </v-col>
      </v-row>
      <v-row class="align-center pa-4" no-gutters>
        <v-col class="pa-4" cols="6">
          <v-icon class="mr-2">mdi-file-document-outline</v-icon
          ><span>Documentation</span>
          <v-divider class="my-2" />
          <v-hover v-slot="{ isHovering, props }">
            <a
              href="https://docs.romm.app"
              target="_blank"
              rel="noopener noreferrer"
              class="text-decoration-none text-primary"
              v-bind="props"
              :class="{
                'text-secondary': isHovering,
              }"
              >Docs</a
            >
          </v-hover>
        </v-col>
        <v-col class="pa-4" cols="6">
          <v-icon class="mr-2">mdi-account-group</v-icon><span>Community</span>
          <v-divider class="my-2" />
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
        </v-col>
      </v-row>
    </template>
  </r-dialog>
</template>
