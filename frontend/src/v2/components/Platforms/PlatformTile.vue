<script setup lang="ts">
// PlatformTile — platform card used by the Home dashboard row (variant="row",
// 150px fixed) and the /platforms grid (variant="grid"). Feature composite
// around RPlatformIcon and the shared Tile chrome; not a primitive.
import { RPlatformIcon } from "@v2/lib";
import { computed, ref } from "vue";
import { useRouter } from "vue-router";
import Tile from "@/v2/components/shared/Tile.vue";
import { usePlatformPlayable } from "@/v2/composables/usePlatformPlayable";
import {
  pendingMorphName,
  useViewTransition,
} from "@/v2/composables/useViewTransition";
import PlayModeBadge from "./PlayModeBadge.vue";

defineOptions({ inheritAttrs: false });

type Variant = "row" | "grid";

interface Props {
  /** Platform slug used to locate /assets/platforms/<slug>.{svg,ico} */
  slug: string;
  /** Filesystem slug (tried first — matches v1's fallback chain). */
  fsSlug?: string;
  displayName: string;
  romCount?: number | null;
  /** Override destination; otherwise derived from `id`. */
  to?: string | object;
  id?: number | string;
  variant?: Variant;
}

const props = withDefaults(defineProps<Props>(), {
  fsSlug: undefined,
  romCount: null,
  to: undefined,
  id: undefined,
  variant: "row",
});

const href = computed(() => props.to ?? `/platform/${props.id ?? ""}`);

// Shared-element morph between the platform tile icon and the
// RPlatformIcon shown in the Platform view's InfoPanel cover slot.
const router = useRouter();
const iconEl = ref<HTMLElement | null>(null);
const { morphTransition } = useViewTransition();

const morphName = computed(() =>
  props.id != null ? `platform-icon-${props.id}` : null,
);

function onTileClick(e: MouseEvent) {
  if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0) {
    return;
  }
  if (!iconEl.value || !morphName.value) return;
  const target = href.value;
  if (typeof target !== "string") return;
  e.preventDefault();
  morphTransition({ el: iconEl.value, name: morphName.value }, async () => {
    await router.push(target);
  });
}

const morphStyle = computed(() =>
  morphName.value && pendingMorphName.value === morphName.value
    ? { viewTransitionName: morphName.value }
    : undefined,
);

const { emulator, mode, streamLabel } = usePlatformPlayable(() => props.slug);
</script>

<template>
  <Tile
    :to="href"
    v-bind="$attrs"
    :row="variant === 'row'"
    :focus-key="id != null ? `platform-${id}` : undefined"
    @click="onTileClick"
  >
    <template #icon>
      <div ref="iconEl" class="plat-tile__icon-inner" :style="morphStyle">
        <RPlatformIcon
          :slug="slug"
          :fs-slug="fsSlug"
          :alt="displayName"
          size="100%"
          :show-tooltip="false"
        />
      </div>
    </template>
    <template v-if="mode" #badge>
      <PlayModeBadge
        class="plat-tile__playable"
        :mode="mode"
        :emulator="emulator"
        :stream-label="streamLabel"
        :size="16"
      />
    </template>
    {{ displayName }}
    <template v-if="romCount != null" #count>
      {{ romCount }} {{ romCount === 1 ? "game" : "games" }}
    </template>
  </Tile>
</template>

<style scoped>
.plat-tile__icon-inner {
  width: 100%;
  height: 100%;
  display: grid;
  place-items: center;
}

.plat-tile__playable {
  position: absolute;
  right: 8px;
  top: 8px;
}
</style>
