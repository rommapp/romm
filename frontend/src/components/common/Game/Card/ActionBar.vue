<script setup lang="ts">
import AdminMenu from "@/components/common/Game/AdminMenu.vue";
import romApi from "@/services/api/rom";
import storeDownload from "@/stores/download";
import storeHeartbeat from "@/stores/heartbeat";
import type { SimpleRom } from "@/stores/roms";
import type { Events } from "@/types/emitter";
import {
  isEJSEmulationSupported,
  isRuffleEmulationSupported,
  is3DSCIARom,
} from "@/utils";
import type { Emitter } from "mitt";
import { computed, inject } from "vue";

// Props
const props = defineProps<{ rom: SimpleRom }>();
const downloadStore = storeDownload();
const heartbeatStore = storeHeartbeat();
const emitter = inject<Emitter<Events>>("emitter");

const ejsEmulationSupported = computed(() => {
  return isEJSEmulationSupported(props.rom.platform_slug, heartbeatStore.value);
});

const ruffleEmulationSupported = computed(() => {
  return isRuffleEmulationSupported(
    props.rom.platform_slug,
    heartbeatStore.value,
  );
});

const is3DSRom = computed(() => {
  return is3DSCIARom(props.rom);
});
</script>

<template>
  <v-row no-gutters>
    <v-col class="d-flex">
      <v-btn
        class="action-bar-btn-small flex-grow-1"
        size="x-small"
        :disabled="downloadStore.value.includes(rom.id)"
        icon="mdi-download"
        variant="text"
        rounded="0"
        @click.prevent="romApi.downloadRom({ rom })"
      />
    </v-col>
    <v-col
      v-if="ejsEmulationSupported || ruffleEmulationSupported"
      class="d-flex"
    >
      <v-btn
        v-if="ejsEmulationSupported"
        @click.prevent
        class="action-bar-btn-small flex-grow-1"
        size="x-small"
        @click="
          $router.push({
            name: 'emulatorjs',
            params: { rom: rom?.id },
          })
        "
        icon="mdi-play"
        variant="text"
        rounded="0"
      />
      <v-btn
        v-if="ruffleEmulationSupported"
        @click.prevent
        class="action-bar-btn-small flex-grow-1"
        size="x-small"
        @click="
          $router.push({
            name: 'ruffle',
            params: { rom: rom?.id },
          })
        "
        icon="mdi-play"
        variant="text"
        rounded="0"
      />
    </v-col>
    <v-col v-if="is3DSRom" class="d-flex">
      <v-btn
        @click.prevent
        class="action-bar-btn-small flex-grow-1"
        size="x-small"
        @click="emitter?.emit('showQRCodeDialog', rom)"
        icon="mdi-qrcode"
        variant="text"
        rounded="0"
      />
    </v-col>
    <v-col class="d-flex">
      <v-menu location="bottom">
        <template #activator="{ props }">
          <v-btn
            @click.prevent
            class="action-bar-btn-small flex-grow-1"
            size="x-small"
            v-bind="props"
            icon="mdi-dots-vertical"
            variant="text"
            rounded="0"
          />
        </template>
        <admin-menu :rom="rom" />
      </v-menu>
    </v-col>
  </v-row>
</template>

<style scoped>
.action-bar-btn-small {
  max-height: 30px;
  width: unset;
}
</style>
