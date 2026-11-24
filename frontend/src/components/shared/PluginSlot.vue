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

/* The action row's buttons are styled by the shared button's own stylesheet,
   which is scoped to that component and cannot reach a button rendered here.
   What a plugin adds therefore has to paint itself into the same row: the same
   circle, the same glass, the same ladder, or it reads as bare glyphs beside
   RomM's own. */
.r-game-btn--action-plugin {
  appearance: none;
  box-sizing: border-box;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  border: 1px solid var(--r-color-border-strong);
  border-radius: 50%;
  background: var(--r-color-surface);
  color: var(--r-color-fg-secondary);
  backdrop-filter: blur(20px);
  cursor: pointer;
  transition:
    background 120ms ease,
    color 120ms ease;
}

.r-game-btn--action-plugin:hover {
  background: var(--r-color-surface-hover);
  color: var(--r-color-fg);
}

.r-game-btn--action-plugin.r-game-btn--default {
  width: 40px;
  height: 40px;
}

.r-game-btn--action-plugin.r-game-btn--large {
  width: 44px;
  height: 44px;
}

.r-game-btn--action-plugin.r-game-btn--default .r-icon {
  font-size: 20px;
}

.r-game-btn--action-plugin.r-game-btn--large .r-icon {
  font-size: 22px;
}

.r-game-btn--action-plugin .r-game-btn__img {
  width: 20px;
  height: 20px;
  border-radius: 4px;
}

.plugin-slot__logo {
  width: 18px;
  height: 18px;
  object-fit: contain;
}
</style>
