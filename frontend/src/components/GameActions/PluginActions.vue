<script setup lang="ts">
// PluginActions: the buttons installed plugins add to a game, in the details
// action ribbon. Each opens the URL its manifest declares, so a custom scheme
// reaches the OS handler and a web URL opens like any link. The label, icon and
// logo come from the manifest, which is why they are not translated.
import { usePluginActions } from "@/composables/usePluginActions";
import { RIcon, RTooltip } from "@/lib";
import type { SimpleRom } from "@/stores/roms";

const props = defineProps<{
  rom: SimpleRom;
  size: "default" | "large";
}>();

const { actions, open } = usePluginActions(() => props.rom);
</script>

<template>
  <button
    v-for="action in actions"
    :key="`${action.pluginId}:${action.id}`"
    type="button"
    class="r-game-btn r-game-btn--surface r-game-btn--action-plugin"
    :class="`r-game-btn--${size}`"
    :aria-label="action.label"
    @click="open(action)"
  >
    <img
      v-if="action.image"
      :src="action.image"
      :alt="action.label"
      class="r-game-btn__img"
    />
    <RIcon v-else :icon="action.icon" />
    <RTooltip activator="parent" :text="action.label" location="top" />
  </button>
</template>
