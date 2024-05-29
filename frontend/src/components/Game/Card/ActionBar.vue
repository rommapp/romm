<script setup lang="ts">
import romApi from "@/services/api/rom";
import storeDownload from "@/stores/download";
import storeAuth from "@/stores/auth";
import AdminMenu from "@/components/Game/AdminMenu/Base.vue";
import type { SimpleRom } from "@/stores/roms";
import { ejsCoresMap } from "@/utils";

// Props
defineProps<{ rom: SimpleRom }>();
const auth = storeAuth();
const downloadStore = storeDownload();
</script>

<template>
  <v-row no-gutters>
    <v-col class="pa-0">
      <v-btn
        class="action-bar-btn"
        @click="romApi.downloadRom({ rom })"
        :disabled="downloadStore.value.includes(rom.id)"
        icon="mdi-download"
        size="x-small"
        rounded="0"
        variant="text"
      />
      <v-btn
        v-if="rom.platform_slug.toLowerCase() in ejsCoresMap"
        class="action-bar-btn"
        :href="`/play/${rom.id}`"
        icon="mdi-play"
        size="x-small"
        rounded="0"
        variant="text"
      />
    </v-col>
    <v-menu location="bottom">
      <template v-slot:activator="{ props }">
        <v-btn
          class="action-bar-btn"
          :disabled="!auth.scopes.includes('roms.write')"
          v-bind="props"
          icon="mdi-dots-vertical"
          size="x-small"
          rounded="0"
          variant="text"
        />
      </template>
      <admin-menu :rom="rom" />
    </v-menu>
  </v-row>
</template>

<style scoped>
.action-bar-btn {
  max-width: 27px;
  max-height: 27px;
}
</style>
