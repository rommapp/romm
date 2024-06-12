<script setup lang="ts">
import romApi from "@/services/api/rom";
import storeDownload from "@/stores/download";
import storeAuth from "@/stores/auth";
import AdminMenu from "@/components/Game/AdminMenu.vue";
import storeGalleryView from "@/stores/galleryView";
import type { SimpleRom } from "@/stores/roms";
import { isEmulationSupported } from "@/utils";
import { storeToRefs } from "pinia";

// Props
defineProps<{ rom: SimpleRom }>();
const auth = storeAuth();
const downloadStore = storeDownload();
const galleryViewStore = storeGalleryView();
const { currentView } = storeToRefs(galleryViewStore);
</script>

<template>
  <v-row no-gutters>
    <v-col>
      <v-btn
        :class="{ 'action-bar-btn-small': currentView == 0 }"
        :size="currentView == 0 ? 'x-small' : 'small'"
        :disabled="downloadStore.value.includes(rom.id)"
        icon="mdi-download"
        rounded="0"
        variant="text"
        @click="romApi.downloadRom({ rom })"
      />
      <v-btn
        v-if="isEmulationSupported(rom.platform_slug)"
        :class="{ 'action-bar-btn-small': currentView == 0 }"
        :size="currentView == 0 ? 'x-small' : 'small'"
        @click="
          $router.push({
            name: 'play',
            params: { rom: rom?.id },
          })
        "
        icon="mdi-play"
        rounded="0"
        variant="text"
      />
    </v-col>
    <v-menu location="bottom">
      <template #activator="{ props }">
        <v-btn
          v-if="auth.scopes.includes('roms.write')"
          :class="{ 'action-bar-btn-small': currentView == 0 }"
          :size="currentView == 0 ? 'x-small' : 'small'"
          v-bind="props"
          icon="mdi-dots-vertical"
          rounded="0"
          variant="text"
        />
      </template>
      <admin-menu :rom="rom" />
    </v-menu>
  </v-row>
</template>

<style scoped>
.action-bar-btn-small {
  max-width: 27px;
  max-height: 27px;
}
</style>
