<script setup lang="ts">
import AdminMenu from "@/components/common/Game/AdminMenu.vue";
import romApi from "@/services/api/rom";
import storeDownload from "@/stores/download";
import storeHeartbeat from "@/stores/heartbeat";
import storeConfig from "@/stores/config";
import type { SimpleRom } from "@/stores/roms";
import storeAuth from "@/stores/auth";
import type { Events } from "@/types/emitter";
import {
  isEJSEmulationSupported,
  isRuffleEmulationSupported,
  is3DSCIARom,
} from "@/utils";
import { ROUTES } from "@/plugins/router";
import type { Emitter } from "mitt";
import { computed, inject, ref, watch } from "vue";
import { storeToRefs } from "pinia";

// Props
const props = defineProps<{ rom: SimpleRom; sizeActionBar: number }>();
const emit = defineEmits(["menu-open", "menu-close"]);
const downloadStore = storeDownload();
const heartbeatStore = storeHeartbeat();
const emitter = inject<Emitter<Events>>("emitter");
const configStore = storeConfig();
const { config } = storeToRefs(configStore);
const auth = storeAuth();

const computedSize = computed(() => {
  return props.sizeActionBar === 1 ? "small" : "x-small";
});

const platformSlug = computed(() => {
  return props.rom.platform_slug in config.value.PLATFORMS_VERSIONS
    ? config.value.PLATFORMS_VERSIONS[props.rom.platform_slug]
    : props.rom.platform_slug;
});

const ejsEmulationSupported = computed(() => {
  return isEJSEmulationSupported(platformSlug.value, heartbeatStore.value);
});

const ruffleEmulationSupported = computed(() => {
  return isRuffleEmulationSupported(platformSlug.value, heartbeatStore.value);
});

const is3DSRom = computed(() => {
  return is3DSCIARom(props.rom);
});

const menuOpen = ref(false);

watch(menuOpen, (val) => {
  emit(val ? "menu-open" : "menu-close");
});
</script>

<template>
  <v-row no-gutters>
    <v-col class="d-flex">
      <v-btn
        class="action-bar-btn-small flex-grow-1"
        :size="computedSize"
        :disabled="downloadStore.value.includes(rom.id)"
        icon="mdi-download"
        variant="text"
        rounded="0"
        @click.prevent="romApi.downloadRom({ rom })"
        :aria-label="`Download ${rom.name}`"
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
        :size="computedSize"
        @click="
          $router.push({
            name: ROUTES.EMULATORJS,
            params: { rom: rom?.id },
          })
        "
        icon="mdi-play"
        variant="text"
        rounded="0"
        :aria-label="`Play ${rom.name}`"
      />
      <v-btn
        v-if="ruffleEmulationSupported"
        @click.prevent
        class="action-bar-btn-small flex-grow-1"
        :size="computedSize"
        @click="
          $router.push({
            name: ROUTES.RUFFLE,
            params: { rom: rom?.id },
          })
        "
        icon="mdi-play"
        variant="text"
        rounded="0"
        :aria-label="`Play ${rom.name}`"
      />
    </v-col>
    <v-col v-if="is3DSRom" class="d-flex">
      <v-btn
        @click.prevent
        class="action-bar-btn-small flex-grow-1"
        :size="computedSize"
        @click="emitter?.emit('showQRCodeDialog', rom)"
        icon="mdi-qrcode"
        variant="text"
        rounded="0"
        :aria-label="`Show ${rom.name} QR code`"
      />
    </v-col>
    <v-col
      v-if="
        auth.scopes.includes('roms.write') ||
        auth.scopes.includes('roms.user.write') ||
        auth.scopes.includes('collections.write')
      "
      class="d-flex"
    >
      <v-menu location="bottom" v-model="menuOpen">
        <template #activator="{ props }">
          <v-btn
            @click.prevent
            class="action-bar-btn-small flex-grow-1"
            :size="computedSize"
            v-bind="props"
            icon="mdi-dots-vertical"
            variant="text"
            rounded="0"
            :aria-label="`${rom.name} admin menu`"
          />
        </template>
        <admin-menu :rom="rom" />
      </v-menu>
    </v-col>
  </v-row>
</template>

<style scoped>
.action-bar-btn-small {
  max-height: 250px;
  width: unset;
}
</style>
