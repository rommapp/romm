<script setup lang="ts">
// Platform gallery — thin orchestrator around `GalleryShell`. Owns the
// platform-specific load flow (route param → ensure platforms loaded →
// setCurrentPlatform → fetchWindowAt(0)) and fills the shell's
// `#header` slot with an InfoPanel. Everything else (virtualizer,
// toolbar, AlphaStrip, dwell, scroll restoration, list mode) lives in
// the shell so any cross-view fix lands once for all three views.
import { RChip, RPlatformIcon } from "@v2/lib";
import { storeToRefs } from "pinia";
import { computed, nextTick, onMounted, ref, watch } from "vue";
import { onBeforeRouteUpdate, useRoute } from "vue-router";
import storePlatforms, { type Platform } from "@/stores/platforms";
import { formatBytes } from "@/utils";
import GalleryShell from "@/v2/components/Gallery/GalleryShell.vue";
import InfoPanel from "@/v2/components/Gallery/InfoPanel.vue";
import Stat from "@/v2/components/shared/Stat.vue";
import storeGalleryRoms from "@/v2/stores/galleryRoms";

const route = useRoute();
const platformsStore = storePlatforms();
const galleryRoms = storeGalleryRoms();
const { currentPlatform, total } = storeToRefs(galleryRoms);

const notFound = ref(false);
const shellRef = ref<InstanceType<typeof GalleryShell> | null>(null);

const tags = computed<string[]>(() => {
  const p = currentPlatform.value as
    | (Platform & {
        category?: string | null;
        family_name?: string | null;
        generation?: number | null;
      })
    | null;
  if (!p) return [];
  const out: string[] = [];
  if (p.category) out.push(p.category);
  if (p.family_name) out.push(p.family_name);
  if (p.generation && p.generation > 0) out.push(`Generation ${p.generation}`);
  return out;
});

type StatRow = { label: string; value: string };
const platformStats = computed<StatRow[]>(() => {
  const p = currentPlatform.value as
    | (Platform & {
        fs_size_bytes?: number | null;
        firmware_count?: number | null;
      })
    | null;
  if (!p) return [];
  const rows: StatRow[] = [
    { label: "In Library", value: String(p.rom_count ?? total.value) },
  ];
  if (p.fs_size_bytes) {
    rows.push({ label: "On Disk", value: formatBytes(p.fs_size_bytes) });
  }
  if (p.firmware_count) {
    rows.push({ label: "Firmware", value: String(p.firmware_count) });
  }
  return rows;
});

async function ensurePlatforms() {
  if (platformsStore.allPlatforms.length === 0) {
    await platformsStore.fetchPlatforms();
  }
}

async function loadForId(platformId: number) {
  await ensurePlatforms();
  const platform = platformsStore.allPlatforms.find((p) => p.id === platformId);
  if (!platform) {
    notFound.value = true;
    return;
  }
  notFound.value = false;
  if (currentPlatform.value?.id !== platform.id) {
    galleryRoms.resetGallery();
    galleryRoms.setCurrentPlatform(platform);
  }
  document.title = platform.display_name;
  // Bootstrap metadata only; grid (shell viewport-sync) and list
  // (GameListRow's onMounted) both hydrate rows per-position from here.
  await galleryRoms.fetchInitialMetadata();
  await nextTick();
  shellRef.value?.applyRestoredScroll();
}

onMounted(() => {
  loadForId(Number(route.params.platform));
});

onBeforeRouteUpdate((to) => {
  // Shell saves the previous route's scroll automatically via its own
  // beforeRouteUpdate guard (runs before this one); we just trigger
  // the new platform's load.
  if (to.name === "platform") loadForId(Number(to.params.platform));
});

watch(
  () => route.params.platform,
  (next) => {
    if (next != null) loadForId(Number(next));
  },
);
</script>

<template>
  <GalleryShell
    ref="shellRef"
    :has-header="!!currentPlatform"
    :search-placeholder="'Filter this platform…'"
    empty-message="No games in this platform yet."
    :not-found="notFound"
    not-found-message="Platform not found."
    :show-platform-badge="false"
    :show-platforms-in-filter="false"
    :skeleton-row-count="4"
  >
    <!-- HEADER (Section 1) — platform InfoPanel: icon + name + stats
         (rom count, on-disk size, firmware count) + category / family /
         generation chips. The shell measures this slot's height
         automatically so the toolbar's natural offset always matches
         the InfoPanel's actual rendered bottom edge. -->
    <template #header>
      <InfoPanel v-if="currentPlatform" :title="currentPlatform.display_name">
        <template #cover>
          <div
            class="r-v2-plat__panel-icon"
            :style="{
              viewTransitionName: `platform-icon-${currentPlatform.id}`,
            }"
          >
            <RPlatformIcon
              :slug="currentPlatform.slug"
              :fs-slug="currentPlatform.fs_slug"
              :alt="currentPlatform.display_name"
              :size="148"
            />
          </div>
        </template>
        <template v-if="tags.length" #tags>
          <RChip
            v-for="t in tags"
            :key="t"
            size="small"
            variant="translucent"
            :rounded="20"
          >
            {{ t }}
          </RChip>
        </template>
        <template v-if="platformStats.length" #stats>
          <Stat
            v-for="s in platformStats"
            :key="s.label"
            :value="s.value"
            :label="s.label"
          />
        </template>
      </InfoPanel>
    </template>
  </GalleryShell>
</template>

<style scoped>
.r-v2-plat__panel-icon {
  width: 200px;
  height: 148px;
  display: grid;
  place-items: center;
}

html[data-bp~="xs"] .r-v2-plat__panel-icon {
  width: 80px;
  height: 60px;
}
</style>
