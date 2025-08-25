<template>
  <div class="flex items-center gap-6 text-white/70 text-[12px]">
    <!-- Controller Mode -->
    <template v-if="hasController">
      <div v-if="showNavigation" class="flex items-center gap-2">
        <DPadIcon class="w-8 h-8 opacity-80" />
        <span class="font-medium tracking-wide">Navigation</span>
      </div>
      <div v-if="showSelect" class="flex items-center gap-2">
        <FaceButtons highlight="south" />
        <span class="font-medium tracking-wide">Select</span>
      </div>
      <div v-if="showBack" class="flex items-center gap-2">
        <FaceButtons highlight="east" />
        <span class="font-medium tracking-wide">Back</span>
      </div>
      <div v-if="showToggleFavorite" class="flex items-center gap-2">
        <FaceButtons highlight="north" />
        <span class="font-medium tracking-wide">Favorite</span>
      </div>
      <div v-if="showMenu" class="flex items-center gap-2">
        <FaceButtons highlight="west" />
        <span class="font-medium tracking-wide">Menu</span>
      </div>
      <div v-if="showDelete" class="flex items-center gap-2">
        <FaceButtons highlight="west" />
        <span class="font-medium tracking-wide">Delete</span>
      </div>
    </template>
    <!-- Keyboard Mode -->
    <template v-else>
      <div v-if="showNavigation" class="flex items-center gap-2">
        <ArrowKeysIcon />
        <span class="font-medium tracking-wide">Navigation</span>
      </div>
      <div v-if="showSelect" class="flex items-center gap-2">
        <span class="keycap">Enter</span>
        <span class="font-medium tracking-wide">Select</span>
      </div>
      <div v-if="showBack" class="flex items-center gap-2">
        <span class="keycap">Bkspc</span>
        <span class="font-medium tracking-wide">Back</span>
      </div>
      <div v-if="showToggleFavorite" class="flex items-center gap-2">
        <span class="keycap">F</span>
        <span class="font-medium tracking-wide">Favorite</span>
      </div>
      <div v-if="showMenu" class="flex items-center gap-2">
        <span class="keycap">X</span>
        <span class="font-medium tracking-wide">Menu</span>
      </div>
      <div v-if="showDelete" class="flex items-center gap-2">
        <span class="keycap">X</span>
        <span class="font-medium tracking-wide">Delete</span>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref, defineComponent, h } from "vue";
/* eslint-disable vue/one-component-per-file */

interface Props {
  showNavigation?: boolean;
  showSelect?: boolean;
  showBack?: boolean;
  showToggleFavorite?: boolean;
  showMenu?: boolean;
  showDelete?: boolean;
}

withDefaults(defineProps<Props>(), {
  showNavigation: true,
  showSelect: true,
  showBack: true,
  showToggleFavorite: false,
  showMenu: false,
  showDelete: false,
});

const hasController = ref(false);
let rafId = 0;

function poll() {
  const pads = navigator.getGamepads?.() || [];
  hasController.value = pads.some((p) => p && p.connected);
  rafId = requestAnimationFrame(poll);
}
onMounted(() => {
  window.addEventListener("gamepadconnected", pollOnce);
  window.addEventListener("gamepaddisconnected", pollOnce);
  poll();
});
onUnmounted(() => {
  cancelAnimationFrame(rafId);
  window.removeEventListener("gamepadconnected", pollOnce);
  window.removeEventListener("gamepaddisconnected", pollOnce);
});
function pollOnce() {
  poll();
}

// Icons rendered via render functions (no runtime template compilation needed)
const DPadIcon = defineComponent({
  name: "DPadIcon",
  setup() {
    return () =>
      h("svg", { viewBox: "0 0 40 40", class: "text-white/70", fill: "none" }, [
        h("rect", {
          x: 16,
          y: 4,
          width: 8,
          height: 12,
          rx: 2,
          class: "fill-white/70",
        }),
        h("rect", {
          x: 16,
          y: 24,
          width: 8,
          height: 12,
          rx: 2,
          class: "fill-white/70",
        }),
        h("rect", {
          x: 4,
          y: 16,
          width: 12,
          height: 8,
          rx: 2,
          class: "fill-white/70",
        }),
        h("rect", {
          x: 24,
          y: 16,
          width: 12,
          height: 8,
          rx: 2,
          class: "fill-white/70",
        }),
        h("rect", {
          x: 16,
          y: 16,
          width: 8,
          height: 8,
          rx: 2,
          class: "fill-white/40",
        }),
      ]);
  },
});

const FaceButtons = defineComponent({
  name: "FaceButtons",
  props: { highlight: { type: String, default: "south" } },
  setup(props) {
    // Render as SVG for crisp alignment; monochrome circles, filled highlight
    const mapping: Record<string, { cx: number; cy: number }> = {
      north: { cx: 12, cy: 4 },
      south: { cx: 12, cy: 20 },
      west: { cx: 4, cy: 12 },
      east: { cx: 20, cy: 12 },
    };
    const order = ["north", "south", "west", "east"] as const;
    return () =>
      h(
        "svg",
        {
          viewBox: "0 0 24 24",
          class: "w-8 h-8 text-white/70 translate-y-[1px]",
        },
        order.map((b) =>
          h("circle", {
            key: b,
            cx: mapping[b].cx,
            cy: mapping[b].cy,
            r: 4,
            class: b === props.highlight ? "fill-white/70" : "fill-white/15",
          })
        )
      );
  },
});

// Keyboard arrow cluster icon (render function)
const ArrowKeysIcon = defineComponent({
  name: "ArrowKeysIcon",
  setup() {
    const key = (x: number, y: number, arrowPath: string) =>
      h("g", [
        h("rect", {
          x,
          y,
          width: 12,
          height: 12,
          rx: 2,
          class: "fill-white/10 stroke-white/25",
          "stroke-width": "0.5",
        }),
        h("path", {
          d: arrowPath,
          class: "fill-white/70",
          transform: `translate(${x + 6}, ${y + 6})`,
        }),
      ]);

    // Arrow paths centered at origin
    const arrows = {
      up: "M 0 -3 L -2 -1 L -1 -1 L -1 3 L 1 3 L 1 -1 L 2 -1 Z",
      down: "M 0 3 L -2 1 L -1 1 L -1 -3 L 1 -3 L 1 1 L 2 1 Z",
      left: "M -3 0 L -1 -2 L -1 -1 L 3 -1 L 3 1 L -1 1 L -1 2 Z",
      right: "M 3 0 L 1 -2 L 1 -1 L -3 -1 L -3 1 L 1 1 L 1 2 Z",
    };

    return () =>
      h(
        "svg",
        {
          viewBox: "0 0 40 28",
          class: "w-10 h-7 text-white/70",
          fill: "none",
          stroke: "currentColor",
        },
        [
          key(14, 1, arrows.up), // Top arrow
          key(1, 14, arrows.left), // Left arrow
          key(14, 14, arrows.down), // Down arrow
          key(27, 14, arrows.right), // Right arrow
        ]
      );
  },
});
</script>

<style scoped>
.keycap {
  background-color: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.2);
  padding: 0.25rem 0.5rem;
  border-radius: 0.25rem;
  font-size: 10px;
  font-family: ui-monospace, SFMono-Regular, "SF Mono", Consolas,
    "Liberation Mono", Menlo, monospace;
  font-weight: 700;
  letter-spacing: 0.05em;
}
</style>
