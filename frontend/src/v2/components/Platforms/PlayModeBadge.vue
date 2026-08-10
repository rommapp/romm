<script setup lang="ts">
// PlayModeBadge - the play marker on a platform surface. Green for the
// in-browser player, romm-blue for streaming, and a diagonal split when a
// platform offers both. Feature composite shared by PlatformTile and
// PlatformListRow so the two surfaces cannot drift apart.
import { computed } from "vue";
import {
  type PlatformEmulator,
  type PlatformPlayMode,
  playTooltip,
} from "@/v2/composables/usePlatformPlayable";
import RIcon from "@/v2/lib/primitives/RIcon/RIcon.vue";
import RTooltip from "@/v2/lib/structural/RTooltip/RTooltip.vue";

defineOptions({ inheritAttrs: false });

interface Props {
  mode: Exclude<PlatformPlayMode, null>;
  emulator?: PlatformEmulator;
  streamLabel?: string | null;
  size?: number;
}

const props = withDefaults(defineProps<Props>(), {
  emulator: null,
  streamLabel: null,
  size: 16,
});

const label = computed(() =>
  playTooltip(props.mode, props.emulator, props.streamLabel),
);

// RIcon hides itself from assistive tech, so the wrapper carries the name.
const sizePx = computed(() => `${props.size}px`);
</script>

<template>
  <span
    v-bind="$attrs"
    class="play-mode-badge"
    :style="{ width: sizePx, height: sizePx }"
    role="img"
    :aria-label="label"
  >
    <RIcon
      icon="mdi-play-circle"
      :size="size"
      :color="mode === 'stream' ? 'romm-blue' : 'success'"
    />
    <RIcon
      v-if="mode === 'both'"
      class="play-mode-badge__over"
      icon="mdi-play-circle"
      :size="size"
      color="romm-blue"
    />
    <RTooltip activator="parent" :text="label" location="top" />
  </span>
</template>

<style scoped>
.play-mode-badge {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  line-height: 0;
}

/* The streaming half is the lower-right triangle of the same glyph, so the
   split runs corner to corner and the play triangle stays knocked out on
   both halves whatever sits behind the badge. */
.play-mode-badge__over {
  position: absolute;
  inset: 0;
  clip-path: polygon(100% 0, 100% 100%, 0 100%);
}
</style>
