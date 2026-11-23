<script setup lang="ts">
// PluginSlot: one place plugins may add something. A surface that offers an
// extension point mounts this with the slot's name, so a new surface is a
// manifest value and a mount rather than another component. Two shapes cover
// the surfaces today: icon buttons for a game's action row, and labelled rows
// for lists such as navigation or Settings.
import { computed } from "vue";
import {
  usePluginActions,
  type PluginAction,
} from "@/composables/usePluginActions";
import { RIcon, RTooltip } from "@/lib";
import type { SimpleRom } from "@/stores/roms";

const props = withDefaults(
  defineProps<{
    slot: string;
    rom?: SimpleRom | null;
    size?: "default" | "large";
    labelled?: boolean;
  }>(),
  { rom: null, size: "default", labelled: false },
);

const { forSlot, open } = usePluginActions(() => props.rom ?? null);
const actions = computed<PluginAction[]>(() => forSlot(props.slot));
</script>

<template>
  <ul v-if="labelled" class="plugin-slot">
    <li v-for="action in actions" :key="`${action.pluginId}:${action.id}`">
      <a
        class="plugin-slot__row"
        :href="action.href"
        :target="action.open === 'same-tab' ? undefined : '_blank'"
        :rel="action.open === 'same-tab' ? undefined : 'noopener noreferrer'"
      >
        <img
          v-if="action.image"
          :src="action.image"
          :alt="action.label"
          class="plugin-slot__logo"
        />
        <RIcon v-else :icon="action.icon" />
        <span>{{ action.label }}</span>
      </a>
    </li>
  </ul>

  <template v-else>
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
</template>

<style scoped>
.plugin-slot {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.plugin-slot__row {
  display: flex;
  align-items: center;
  gap: 8px;
  color: inherit;
  text-decoration: none;
}

.plugin-slot__row:hover {
  text-decoration: underline;
}

.plugin-slot__logo {
  width: 18px;
  height: 18px;
  object-fit: contain;
}
</style>
