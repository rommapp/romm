<script setup lang="ts">
import AdminMenu from "@/components/common/Game/AdminMenu.vue";
import romApi from "@/services/api/rom";
import storeDownload from "@/stores/download";
import type { SimpleRom } from "@/stores/roms";
import { isEmulationSupported } from "@/utils";

// Props
defineProps<{ rom: SimpleRom }>();
const downloadStore = storeDownload();
</script>

<template>
  <v-row no-gutters>
    <v-col>
      <v-btn
        class="action-bar-btn-small"
        size="x-small"
        :disabled="downloadStore.value.includes(rom.id)"
        icon="mdi-download"
        rounded="0"
        variant="text"
        @click="romApi.downloadRom({ rom })"
      />
    </v-col>
    <v-col>
      <v-btn
        v-if="isEmulationSupported(rom.platform_slug)"
        class="action-bar-btn-small"
        size="x-small"
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
          class="action-bar-btn-small"
          size="x-small"
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
  max-width: 22px;
  max-height: 30px;
}
</style>
