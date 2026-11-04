<script setup lang="ts">
// PlatformTile: platform card used by the Home dashboard row (variant="row",
// 150px fixed) and the /platforms grid (variant="grid"). Feature composite
// around PlatformIcon and the shared Tile chrome; not a primitive.
import { computed, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useRouter } from "vue-router";
import { prettifyPlatformCategory } from "@/components/Platforms/platformListColumns";
import PlatformIcon from "@/components/shared/PlatformIcon.vue";
import Tile from "@/components/shared/Tile.vue";
import { useBreakpoint } from "@/composables/useBreakpoint";
import { usePlatformPlayable } from "@/composables/usePlatformPlayable";
import {
  pendingMorphName,
  useViewTransition,
} from "@/composables/useViewTransition";
import { RImage } from "@/lib";
import { shippedPlatformIconUrl } from "@/utils/platformIcons";
import PlayModeBadge from "./PlayModeBadge.vue";

defineOptions({ inheritAttrs: false });

type Variant = "row" | "grid";

interface Props {
  /** Platform slug used to pick the shipped icon. */
  slug: string;
  /** Filesystem slug, used when no icon ships for `slug`. */
  fsSlug?: string | undefined;
  displayName: string;
  romCount?: number | null;
  artworkUrl?: string | null | undefined;
  category?: string | null | undefined;
  firstReleaseYear?: number | null | undefined;
  /** Override destination; otherwise derived from `id`. */
  to?: string | object | undefined;
  id?: number | string | undefined;
  variant?: Variant;
}

const props = withDefaults(defineProps<Props>(), {
  fsSlug: undefined,
  romCount: null,
  artworkUrl: null,
  category: null,
  firstReleaseYear: null,
  to: undefined,
  id: undefined,
  variant: "row",
});

const useProviderArtwork = computed(
  () =>
    props.variant === "grid" &&
    props.artworkUrl &&
    !shippedPlatformIconUrl(props.slug) &&
    !(props.fsSlug && shippedPlatformIconUrl(props.fsSlug)),
);

const href = computed(() => props.to ?? `/platform/${props.id ?? ""}`);
const { xs } = useBreakpoint();
const artworkSize = computed(() => (xs.value ? 88 : 120));
const discoveryMetadata = computed(() =>
  [
    props.firstReleaseYear,
    props.category && prettifyPlatformCategory(props.category),
  ]
    .filter(Boolean)
    .join(" · "),
);

const { t } = useI18n();

// Shared-element morph between the platform tile icon and the
// PlatformIcon shown in the Platform view's InfoPanel cover slot.
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
  <!-- `plat-tile` is the cell selector PlatformsIndex's spatial nav walks. -->
  <Tile
    :to="href"
    v-bind="$attrs"
    class="plat-tile"
    :class="{ 'plat-tile--discovery': variant === 'grid' }"
    :row="variant === 'row'"
    :focus-key="id != null ? `platform-${id}` : undefined"
    @click="onTileClick"
  >
    <template #icon>
      <div ref="iconEl" class="plat-tile__icon-inner" :style="morphStyle">
        <RImage
          v-if="useProviderArtwork"
          :src="artworkUrl ?? undefined"
          :alt="displayName"
          :width="artworkSize"
          :height="artworkSize"
          contain
        >
          <template #loading>
            <PlatformIcon
              :slug="slug"
              :fs-slug="fsSlug"
              :alt="displayName"
              :size="72"
              :show-tooltip="false"
            />
          </template>
          <template #error>
            <PlatformIcon
              :slug="slug"
              :fs-slug="fsSlug"
              :alt="displayName"
              :size="72"
              :show-tooltip="false"
            />
          </template>
        </RImage>
        <PlatformIcon
          v-else
          :slug="slug"
          :fs-slug="fsSlug"
          :alt="displayName"
          :size="variant === 'grid' ? artworkSize : '100%'"
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
    <template
      v-if="romCount != null || (variant === 'grid' && discoveryMetadata)"
      #count
    >
      <span
        v-if="variant === 'grid' && discoveryMetadata"
        class="plat-tile__metadata"
        >{{ discoveryMetadata }}</span
      >
      <span v-if="romCount != null">{{
        t("collection.games-count", romCount, { named: { n: romCount } })
      }}</span>
    </template>
  </Tile>
</template>

<style scoped>
.plat-tile--discovery :deep(.r-tile__icon) {
  width: 100%;
  height: 120px;
  overflow: hidden;
}

.plat-tile--discovery .plat-tile__icon-inner {
  height: 120px;
}

.plat-tile--discovery :deep(.r-tile__count) {
  display: grid;
  gap: var(--r-space-2);
  margin-top: auto;
  text-align: center;
}

.plat-tile__metadata {
  color: var(--r-color-fg-secondary);
}

html[data-bp~="xs"] .plat-tile--discovery :deep(.r-tile__icon),
html[data-bp~="xs"] .plat-tile--discovery .plat-tile__icon-inner {
  width: 100%;
  height: 88px;
}

.plat-tile__icon-inner {
  width: 100%;
  height: 100%;
  min-width: 0;
  min-height: 0;
  display: grid;
  place-items: center;
}

.plat-tile__playable {
  position: absolute;
  right: 8px;
  top: 8px;
}
</style>
