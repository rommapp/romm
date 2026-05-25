<script setup lang="ts">
// Home dashboard — composed of primitives + feature components. Each
// section is a CardRow with its own tile type in the default slot.
//
// Gamepad / keyboard arrow navigation: the root is registered with
// `useGridNav`, which treats each CardRow track as a row and its children
// as cells. When the input modality flips to `"pad"` (gamepad detected
// or pressed) we autofocus the first cell so the synthetic keys
// dispatched by `useGamepad` have somewhere to go.
import { RChip, RDivider, RIcon, RSkeletonBlock } from "@v2/lib";
import { storeToRefs } from "pinia";
import { computed, onMounted, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { ROUTES } from "@/plugins/router";
import setupApi, { type SetupLibraryInfo } from "@/services/api/setup";
import storeCollections from "@/stores/collections";
import storePlatforms from "@/stores/platforms";
import storeRoms, { type SimpleRom } from "@/stores/roms";
import CollectionTile from "@/v2/components/Collections/CollectionTile.vue";
import { GameCard, GameCardSkeleton } from "@/v2/components/GameCard";
import CardRow from "@/v2/components/Home/CardRow.vue";
import PlatformTile from "@/v2/components/Platforms/PlatformTile.vue";
import { useGridNav } from "@/v2/composables/useGridNav";
import { useWebpSupport } from "@/v2/composables/useWebpSupport";

const { t } = useI18n();

const romsStore = storeRoms();
const platformsStore = storePlatforms();
const collectionsStore = storeCollections();
const { supportsWebp, toWebp } = useWebpSupport();

const { recentRoms, continuePlayingRoms } = storeToRefs(romsStore);
const { filledPlatforms, fetchingPlatforms } = storeToRefs(platformsStore);
const { allCollections, favoriteCollection, fetchingCollections } =
  storeToRefs(collectionsStore);

const fetchingRecent = ref(false);
const fetchingContinue = ref(false);

const gridRoot = ref<HTMLElement | null>(null);
useGridNav(gridRoot);

onMounted(() => {
  if (platformsStore.allPlatforms.length === 0) {
    platformsStore.fetchPlatforms();
  }
  if (collectionsStore.allCollections.length === 0) {
    collectionsStore.fetchCollections();
  }
  if (recentRoms.value.length === 0) {
    fetchingRecent.value = true;
    romsStore.fetchRecentRoms().finally(() => (fetchingRecent.value = false));
  }
  if (continuePlayingRoms.value.length === 0) {
    fetchingContinue.value = true;
    romsStore
      .fetchContinuePlayingRoms()
      .finally(() => (fetchingContinue.value = false));
  }
});

// True when nothing has been added yet AND we're no longer fetching —
// mirrors v1's EmptyHome check so we don't flash the placeholder while
// the initial loads are still in-flight.
const isEmpty = computed(
  () =>
    !fetchingPlatforms.value &&
    !fetchingCollections.value &&
    !fetchingRecent.value &&
    !fetchingContinue.value &&
    recentRoms.value.length === 0 &&
    continuePlayingRoms.value.length === 0 &&
    filledPlatforms.value.length === 0 &&
    allCollections.value.length === 0,
);

// Filesystem snapshot for the empty state — shows the user what RomM
// can already see on disk so the "run a scan" CTA isn't a leap of
// faith. Fetched lazily the first time the empty state appears; the
// endpoint requires PLATFORMS_READ scope so we fail silently for
// users without it (the chips just stay hidden).
const libraryInfo = ref<SetupLibraryInfo | null>(null);
const fetchingLibraryInfo = ref(false);

const detectedPlatformCount = computed(
  () => libraryInfo.value?.existing_platforms.length ?? 0,
);
const detectedGameCount = computed(() =>
  (libraryInfo.value?.existing_platforms ?? []).reduce(
    (sum, p) => sum + p.rom_count,
    0,
  ),
);

async function loadLibraryInfo() {
  if (libraryInfo.value || fetchingLibraryInfo.value) return;
  fetchingLibraryInfo.value = true;
  try {
    const { data } = await setupApi.getLibraryInfo();
    libraryInfo.value = data;
  } catch {
    // Endpoint is permission-gated; non-admins fall through silently
    // and the chips just stay hidden.
  } finally {
    fetchingLibraryInfo.value = false;
  }
}

watch(
  isEmpty,
  (empty) => {
    if (empty) void loadLibraryInfo();
  },
  { immediate: true },
);

// Favorite ROMs — derived from the Favorites collection's rom_ids.
// eslint-disable-next-line @typescript-eslint/no-unused-vars -- false positive: used in <template>; @typescript-eslint+projectService doesn't see Vue templates
const favoriteRoms = computed<SimpleRom[]>(() => {
  const favIds = favoriteCollection.value?.rom_ids ?? [];
  if (!favIds.length) return [];
  const pool = new Map<number, SimpleRom>();
  for (const r of recentRoms.value) pool.set(r.id, r);
  for (const r of continuePlayingRoms.value) pool.set(r.id, r);
  const out: SimpleRom[] = [];
  for (const id of favIds) {
    const hit = pool.get(id);
    if (hit) out.push(hit);
  }
  return out;
});

// Pick a small set of cover URLs to seed the collection tile mosaic.
function collectionCovers(pathCovers: string[] | undefined): string[] {
  return (pathCovers ?? []).slice(0, 4).map(toWebp);
}
</script>

<template>
  <div ref="gridRoot" class="r-v2-home">
    <!-- Empty library state — shown when nothing has been ingested
         yet. Hides every section underneath so the user lands on a
         decision (upload vs scan), not on a row of skeletons. -->
    <section v-if="isEmpty" class="r-v2-home-empty">
      <div class="r-v2-home-empty__hero">
        <RIcon
          icon="mdi-controller-classic-outline"
          size="72"
          class="r-v2-home-empty__hero-icon"
        />
        <h2 class="r-v2-home-empty__title">
          {{ t("home.empty-headline") }}
        </h2>
        <p class="r-v2-home-empty__hint">{{ t("home.empty-hint") }}</p>

        <!-- Filesystem snapshot — only rendered once /setup/library
             has resolved. Mirrors the chip pair from setup wizard
             step 1 so the user sees the same "RomM detected this on
             disk" telemetry from both entry points. -->
        <div
          v-if="libraryInfo && detectedPlatformCount + detectedGameCount > 0"
          class="r-v2-home-empty__detected"
        >
          <RChip
            size="small"
            variant="translucent"
            color="primary"
            prepend-icon="mdi-gamepad-variant-outline"
          >
            {{
              t(
                "home.empty-detected-platforms",
                { count: detectedPlatformCount },
                detectedPlatformCount,
              )
            }}
          </RChip>
          <RChip size="small" variant="translucent" prepend-icon="mdi-disc">
            {{
              t(
                "home.empty-detected-games",
                { count: detectedGameCount },
                detectedGameCount,
              )
            }}
          </RChip>
        </div>
      </div>

      <div class="r-v2-home-empty__choices">
        <router-link
          :to="{ name: ROUTES.UPLOAD }"
          class="r-v2-home-empty__choice"
        >
          <div class="r-v2-home-empty__choice-icon">
            <RIcon icon="mdi-cloud-upload-outline" size="40" />
          </div>
          <h3 class="r-v2-home-empty__choice-title">
            {{ t("home.empty-upload-title") }}
          </h3>
          <p class="r-v2-home-empty__choice-desc">
            {{ t("home.empty-upload-desc") }}
          </p>
          <span class="r-v2-home-empty__choice-cta">
            {{ t("home.empty-upload-cta") }}
            <RIcon icon="mdi-arrow-right" size="16" />
          </span>
        </router-link>

        <RDivider vertical class="r-v2-home-empty__divider" />

        <router-link
          :to="{ name: ROUTES.SCAN }"
          class="r-v2-home-empty__choice"
        >
          <div class="r-v2-home-empty__choice-icon">
            <RIcon icon="mdi-folder-search-outline" size="40" />
          </div>
          <h3 class="r-v2-home-empty__choice-title">
            {{ t("home.empty-scan-title") }}
          </h3>
          <p class="r-v2-home-empty__choice-desc">
            {{ t("home.empty-scan-desc") }}
          </p>
          <span class="r-v2-home-empty__choice-cta">
            {{ t("home.empty-scan-cta") }}
            <RIcon icon="mdi-arrow-right" size="16" />
          </span>
        </router-link>
      </div>
    </section>

    <template v-else>
      <!-- Continue playing -->
      <CardRow
        v-if="continuePlayingRoms.length || fetchingContinue"
        title="Continue playing"
        :count="continuePlayingRoms.length"
      >
        <template #icon>
          <RIcon icon="mdi-play" size="20" />
        </template>
        <template v-if="fetchingContinue && !continuePlayingRoms.length">
          <GameCardSkeleton v-for="n in 4" :key="`cs-${n}`" hero />
        </template>
        <template v-else>
          <GameCard
            v-for="rom in continuePlayingRoms"
            :key="`cont-${rom.id}`"
            :rom="rom"
            :webp="supportsWebp"
            hero
          />
        </template>
      </CardRow>

      <!-- Recently added -->
      <CardRow title="Recently added" :count="recentRoms.length">
        <template #icon>
          <RIcon icon="mdi-shimmer" size="20" />
        </template>
        <template v-if="fetchingRecent && !recentRoms.length">
          <GameCardSkeleton v-for="n in 6" :key="`rs-${n}`" />
        </template>
        <div v-else-if="!recentRoms.length" class="r-v2-home__empty">
          No games added yet.
        </div>
        <template v-else>
          <GameCard
            v-for="rom in recentRoms"
            :key="`rec-${rom.id}`"
            :rom="rom"
            :webp="supportsWebp"
          />
        </template>
      </CardRow>

      <!-- Favorites -->
      <!-- <CardRow
      v-if="favoriteRoms.length"
      title="Favorites"
      :count="favoriteRoms.length"
    >
      <template #icon>
        <RIcon icon="mdi-heart" size="20" />
      </template>
      <GameCard
        v-for="rom in favoriteRoms"
        :key="`fav-${rom.id}`"
        :rom="rom"
        :webp="supportsWebp"
      />
    </CardRow> -->

      <!-- Platforms -->
      <CardRow title="Platforms" :count="filledPlatforms.length" gap="16px">
        <template #icon>
          <RIcon icon="mdi-controller" size="20" />
        </template>
        <template v-if="fetchingPlatforms && !filledPlatforms.length">
          <RSkeletonBlock
            v-for="n in 8"
            :key="`ps-${n}`"
            width="150px"
            height="140px"
            rounded="card"
          />
        </template>
        <PlatformTile
          v-for="p in filledPlatforms"
          v-else
          :key="`plat-${p.id}`"
          :id="p.id"
          :slug="p.slug"
          :fs-slug="p.fs_slug"
          :display-name="p.display_name"
          :rom-count="p.rom_count"
          variant="row"
        />
      </CardRow>

      <!-- Collections -->
      <CardRow
        v-if="allCollections.length || fetchingCollections"
        title="Collections"
        :count="allCollections.length"
        gap="16px"
      >
        <template #icon>
          <RIcon icon="mdi-bookmark-outline" size="20" />
        </template>
        <CollectionTile
          v-for="c in allCollections"
          :id="c.id"
          :key="`coll-${c.id}`"
          :to="`/collection/${c.id}`"
          :name="c.name"
          :rom-count="c.rom_count"
          :covers="collectionCovers(c.path_covers_small ?? [])"
          variant="row"
        />
      </CardRow>
    </template>
  </div>
</template>

<style scoped>
.r-v2-home {
  padding: 16px 0 48px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.r-v2-home__empty {
  color: var(--r-color-fg-faint);
  font-size: 13px;
  padding: 24px var(--r-row-pad);
}

/* ── Empty library state ─────────────────────────────────────────
   Two-step layout: hero (icon + headline + hint) on top, then a
   two-pane "how do you want to add games" panel split by a vertical
   divider. Each pane is a router-link so the whole panel is the hit
   target — no nested buttons. */
.r-v2-home-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--r-space-8);
  padding: var(--r-space-10) var(--r-space-6);
  min-height: 60vh;
  justify-content: center;
}

.r-v2-home-empty__hero {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--r-space-3);
  text-align: center;
  max-width: 560px;
}

.r-v2-home-empty__hero-icon {
  color: var(--r-color-brand-primary);
  filter: drop-shadow(
    0 0 24px color-mix(in srgb, var(--r-color-brand-primary) 35%, transparent)
  );
  margin-bottom: var(--r-space-1);
}

.r-v2-home-empty__title {
  margin: 0;
  font-size: var(--r-font-size-2xl);
  font-weight: var(--r-font-weight-bold);
  color: var(--r-color-fg);
  letter-spacing: -0.01em;
}

.r-v2-home-empty__hint {
  margin: 0;
  color: var(--r-color-fg-secondary);
  font-size: var(--r-font-size-md);
  line-height: var(--r-line-height-relaxed);
}

.r-v2-home-empty__detected {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: var(--r-space-2);
  margin-top: var(--r-space-2);
}

.r-v2-home-empty__choices {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
  align-items: stretch;
  width: 100%;
  max-width: 880px;
  gap: var(--r-space-6);
  background: var(--r-color-bg-elevated);
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-lg);
  padding: var(--r-space-6);
}

@media (max-width: 720px) {
  .r-v2-home-empty__choices {
    grid-template-columns: minmax(0, 1fr);
    gap: var(--r-space-4);
  }
  .r-v2-home-empty__divider {
    display: none;
  }
}

.r-v2-home-empty__divider {
  align-self: stretch;
}

/* Each choice is a router-link rendered as a card. The "feel" is
   close to a primary CTA — brand-tinted halo on hover, the trailing
   chevron in the CTA line nudges right so the click target reads
   actionable without needing a separate <RBtn>. */
.r-v2-home-empty__choice {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: var(--r-space-3);
  padding: var(--r-space-5);
  border-radius: var(--r-radius-md);
  text-decoration: none;
  color: inherit;
  background: transparent;
  border: 1px solid transparent;
  transition:
    background var(--r-motion-fast) var(--r-motion-ease-out),
    border-color var(--r-motion-fast) var(--r-motion-ease-out),
    transform var(--r-motion-fast) var(--r-motion-ease-out);
}

.r-v2-home-empty__choice:hover,
.r-v2-home-empty__choice:focus-visible {
  background: color-mix(in srgb, var(--r-color-brand-primary) 6%, transparent);
  border-color: color-mix(
    in srgb,
    var(--r-color-brand-primary) 35%,
    transparent
  );
  transform: translateY(-2px);
}

.r-v2-home-empty__choice-icon {
  display: grid;
  place-items: center;
  width: 56px;
  height: 56px;
  border-radius: var(--r-radius-md);
  background: color-mix(in srgb, var(--r-color-brand-primary) 12%, transparent);
  color: var(--r-color-brand-primary);
}

.r-v2-home-empty__choice-title {
  margin: 0;
  font-size: var(--r-font-size-lg);
  font-weight: var(--r-font-weight-semibold);
  color: var(--r-color-fg);
}

.r-v2-home-empty__choice-desc {
  margin: 0;
  color: var(--r-color-fg-secondary);
  font-size: var(--r-font-size-sm);
  line-height: var(--r-line-height-relaxed);
  flex: 1 1 auto;
}

.r-v2-home-empty__choice-cta {
  display: inline-flex;
  align-items: center;
  gap: var(--r-space-1);
  color: var(--r-color-brand-primary);
  font-size: var(--r-font-size-sm);
  font-weight: var(--r-font-weight-semibold);
  margin-top: var(--r-space-1);
  transition: gap var(--r-motion-fast) var(--r-motion-ease-out);
}

.r-v2-home-empty__choice:hover .r-v2-home-empty__choice-cta,
.r-v2-home-empty__choice:focus-visible .r-v2-home-empty__choice-cta {
  gap: var(--r-space-2);
}
</style>
