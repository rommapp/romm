<script setup lang="ts">
// CollectionHead — the collection-context strip that sits above the
// gallery / settings tab body. Mirrors `PlatformHead` in shape: an
// InfoPanel (4-cover mosaic + eyebrow + name + description chip +
// stats) plus the RTabNav underneath. Re-used in two render branches
// inside Collection.vue:
//
//   1. Library tab — passed to `GalleryShell`'s `#header` slot so the
//      head scrolls naturally with the cards (and the toolbar pins
//      below it).
//
//   2. Settings tab — rendered inline above the tab body inside a
//      plain scroll wrapper. The head scrolls together with the
//      tab content.
import { RBtn, RChip, RTabNav } from "@v2/lib";
import type { RTabNavItem } from "@v2/lib";
import { useI18n } from "vue-i18n";
import type {
  Collection,
  SmartCollection,
  VirtualCollection,
} from "@/stores/collections";
import CollectionMosaic from "@/v2/components/Collections/CollectionMosaic.vue";
import InfoPanel from "@/v2/components/Gallery/InfoPanel.vue";
import Stat from "@/v2/components/shared/Stat.vue";

defineOptions({ inheritAttrs: false });

const { t } = useI18n();

type AnyCollection = Collection | VirtualCollection | SmartCollection;

defineProps<{
  collection: AnyCollection;
  /** Kind drives the eyebrow label and the `viewTransitionName` so
   *  shared-element transitions stay stable across the three route
   *  shapes. */
  kind: "regular" | "virtual" | "smart";
  kindLabel: string;
  description: string;
  covers: string[];
  tab: string;
  tabs: RTabNavItem[];
  canDownload: boolean;
  randomLoading?: boolean;
}>();

defineEmits<{
  (e: "update:tab", v: string): void;
  (e: "random"): void;
  (e: "download"): void;
}>();
</script>

<template>
  <InfoPanel :title="collection.name">
    <template #cover>
      <div
        class="r-v2-coll__panel-cover"
        :style="{
          viewTransitionName: `coll-cover-${kind}-${collection.id}`,
        }"
      >
        <CollectionMosaic :covers="covers" aspect-ratio="140 / 188" />
      </div>
    </template>

    <template #eyebrow>
      <span class="r-eyebrow">{{ kindLabel }}</span>
    </template>

    <template v-if="description" #tags>
      <RChip size="small" variant="translucent" :rounded="20">
        {{ description }}
      </RChip>
    </template>

    <template #stats>
      <Stat :value="collection.rom_count" :label="t('common.games')" />
    </template>

    <template #actions>
      <RBtn
        variant="outlined"
        surface
        icon="mdi-shuffle-variant"
        rounded="circle"
        :loading="randomLoading"
        :disabled="collection.rom_count === 0"
        :aria-label="t('platform.random-rom')"
        :tooltip="t('platform.random-rom')"
        @click="$emit('random')"
      />
      <RBtn
        v-if="canDownload"
        variant="outlined"
        surface
        icon="mdi-download"
        rounded="circle"
        :disabled="collection.rom_count === 0"
        :aria-label="t('collection.download-collection')"
        :tooltip="t('collection.download-collection')"
        @click="$emit('download')"
      />
    </template>
  </InfoPanel>

  <RTabNav
    :model-value="tab"
    :items="tabs"
    class="r-v2-coll__tabs"
    @update:model-value="(v) => $emit('update:tab', v)"
  />
</template>

<style scoped>
.r-v2-coll__panel-cover {
  width: var(--r-coll-cover-w);
  height: var(--r-coll-cover-h);
  border-radius: var(--r-radius-lg);
  overflow: hidden;
  box-shadow: var(--r-elev-2);
}

/* Match the collection-index card covers (which fill a ~150px grid cell on
   phones) — the InfoPanel stacks and centres the cover on xs, so there's room
   for a proper hero instead of the old cramped 100px thumbnail. */
html[data-bp~="xs"] .r-v2-coll__panel-cover {
  width: var(--r-coll-cover-w-xs);
  height: var(--r-coll-cover-h-xs);
}

.r-v2-coll__tabs {
  /* Tuck the nav up against the InfoPanel's bottom padding so the
     two read as a single head band — same vocabulary as PlatformHead. */
  margin-top: -8px;
}
</style>
