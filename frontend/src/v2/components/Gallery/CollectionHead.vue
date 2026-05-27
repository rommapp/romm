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
//
// No action ribbon — edit and delete moved inline into the Settings
// tab (editable form + danger zone), matching the Platform layout.
import { RChip, RTabNav } from "@v2/lib";
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
}>();

defineEmits<{
  (e: "update:tab", v: string): void;
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
  width: 140px;
  height: 188px;
  border-radius: var(--r-radius-lg);
  overflow: hidden;
  box-shadow: var(--r-elev-2);
}

html[data-bp~="xs"] .r-v2-coll__panel-cover {
  width: 100px;
  height: 134px;
}

.r-v2-coll__tabs {
  /* Tuck the nav up against the InfoPanel's bottom padding so the
     two read as a single head band — same vocabulary as PlatformHead. */
  margin-top: -8px;
}
</style>
