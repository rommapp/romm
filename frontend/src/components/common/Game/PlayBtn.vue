<script setup lang="ts">
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { computed, inject, useAttrs, ref } from "vue";
import { useRouter } from "vue-router";
import {
  ANIMATION_DELAY,
  useGameAnimation,
} from "@/composables/useGameAnimation";
import { ROUTES } from "@/plugins/router";
import storeConfig from "@/stores/config";
import storeHeartbeat from "@/stores/heartbeat";
import storeRoms, { type SimpleRom } from "@/stores/roms";
import type { Events } from "@/types/emitter";
import { isEJSEmulationSupported, isRuffleEmulationSupported } from "@/utils";

const props = defineProps<{ rom: SimpleRom; iconEmbedded?: boolean }>();
const attrs = useAttrs();
const configStore = storeConfig();
const heartbeatStore = storeHeartbeat();
const romsStore = storeRoms();
const router = useRouter();
const { config } = storeToRefs(configStore);
const { value: heartbeat } = storeToRefs(heartbeatStore);
const emitter = inject<Emitter<Events>>("emitter");

const isEmulationSupported = computed(() => {
  return (
    isEJSEmulationSupported(
      props.rom.platform_slug,
      heartbeat.value,
      config.value,
    ) ||
    isRuffleEmulationSupported(
      props.rom.platform_slug,
      heartbeat.value,
      config.value,
    )
  );
});

const { animateCD, animateCartridge } = useGameAnimation({
  rom: props.rom,
});

async function goToPlayer(rom: SimpleRom) {
  if (
    isEJSEmulationSupported(rom.platform_slug, heartbeat.value, config.value)
  ) {
    emitter?.emit("playGame", rom.id);
    setTimeout(
      async () => {
        await router.push({
          name: ROUTES.EMULATORJS,
          params: { rom: rom.id },
        });
        // Force full reload to retrieve COEP/COOP headers from nginx
        // Required to enable multi-threading in EmulatorJS
        router.go(0);
      },
      animateCD.value || animateCartridge.value ? ANIMATION_DELAY : 0,
    );
  } else if (
    isRuffleEmulationSupported(rom.platform_slug, heartbeat.value, config.value)
  ) {
    await router.push({
      name: ROUTES.RUFFLE,
      params: { rom: rom.id },
    });
  }
}
</script>

<template>
  <template v-if="isEmulationSupported">
    <v-btn
      v-if="iconEmbedded"
      v-bind="attrs"
      :disabled="rom.missing_from_fs"
      :aria-label="`Play ${rom.name}`"
      icon="mdi-play"
      @click="goToPlayer(rom)"
    />
    <v-btn
      v-else
      v-bind="attrs"
      :disabled="rom.missing_from_fs"
      :aria-label="`Play ${rom.name}`"
      @click="goToPlayer(rom)"
    >
      <v-icon>mdi-play</v-icon>
    </v-btn>
  </template>
</template>
