<script setup lang="ts">
import { storeToRefs } from "pinia";
import { computed, useAttrs } from "vue";
import { useRouter } from "vue-router";
import storeConfig from "@/stores/config";
import storeHeartbeat from "@/stores/heartbeat";
import { type SimpleRom } from "@/stores/roms";
import { ROUTES } from "@/plugins/router";
import {
  isAnyEmulationSupported,
  isEJSEmulationSupported,
  isRuffleEmulationSupported,
} from "@/utils";

const props = defineProps<{ rom: SimpleRom; iconEmbedded?: boolean }>();
const attrs = useAttrs();
const configStore = storeConfig();
const heartbeatStore = storeHeartbeat();
const router = useRouter();
const { config } = storeToRefs(configStore);
const { value: heartbeat } = storeToRefs(heartbeatStore);

const isEmulationSupported = computed(() => {
  return isAnyEmulationSupported(
    props.rom.platform_slug,
    heartbeat.value,
    config.value,
  );
});

function goToPlayer(rom: SimpleRom) {
  if (
    isEJSEmulationSupported(rom.platform_slug, heartbeat.value, config.value)
  ) {
    router.push({
      name: ROUTES.EMULATORJS,
      params: { rom: rom.id },
    });
  } else if (
    isRuffleEmulationSupported(rom.platform_slug, heartbeat.value, config.value)
  ) {
    router.push({
      name: ROUTES.RUFFLE,
      params: { rom: rom.id },
    });
  }
}
</script>

<template>
  <v-btn
    v-if="isEmulationSupported && iconEmbedded"
    v-bind="attrs"
    :disabled="rom.missing_from_fs"
    :aria-label="`Play ${rom.name}`"
    icon="mdi-play"
    @click="goToPlayer(rom)"
  />

  <v-btn
    v-if="isEmulationSupported && !iconEmbedded"
    v-bind="attrs"
    :disabled="rom.missing_from_fs"
    :aria-label="`Play ${rom.name}`"
    @click="goToPlayer(rom)"
  >
    <v-icon>mdi-play</v-icon>
  </v-btn>
</template>
