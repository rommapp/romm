<script setup lang="ts">
// OverviewTab — single landing surface for everything that doesn't get
// its own tab. Top to bottom:
//   1. Summary paragraph
//   2. Last-played row (TODO: move into a SaveData tab once it lands)
//   3. Quick facts — PlayerCountBadge + AgeRatingBadges (game-level
//      characteristics, rendered as semantic badges rather than chips)
//   4. RomM Collections — the user's personal collections this ROM
//      lives in, rendered as bookmark-icon chip RouterLinks
//   5. Info grid (Genres / Companies / Franchises / Collections —
//      "Companies" is the API field for merged developer + publisher)
//   6. Screenshots (also reachable via the Media tab's Screenshots subtab,
//      which is where uploads will live)
//   7. HLTB strip
//   8. Related games — a single RCollapsible collapsing all of:
//      Expansions, DLC, Remakes, Remasters, Similar games.
//
// Status enum + flags (now_playing / backlogged / hidden) and personal
// metrics (rating / difficulty / completion) live in the action ribbon
// — see GameActionBtn (status) and MetricMenuBtn.
import { RIcon } from "@v2/lib";
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import type {
  IGDBRelatedGame,
  RomHLTBMetadata,
  UserCollectionSchema,
} from "@/__generated__";
import storeCollections from "@/stores/collections";
import type { DetailedRom } from "@/stores/roms";
import CollectionTile from "@/v2/components/Collections/CollectionTile.vue";
import AgeRatingBadges from "@/v2/components/GameDetails/AgeRatingBadges.vue";
import HLTBStrip from "@/v2/components/GameDetails/HLTBStrip.vue";
import type { InfoGridSection } from "@/v2/components/GameDetails/InfoGrid.vue";
import InfoGrid from "@/v2/components/GameDetails/InfoGrid.vue";
import PlayerCountBadge from "@/v2/components/GameDetails/PlayerCountBadge.vue";
import RelatedGamesGrid from "@/v2/components/GameDetails/RelatedGamesGrid.vue";
import ScreenshotsTab from "@/v2/components/GameDetails/ScreenshotsTab.vue";
import { PROVIDERS, providerId } from "@/v2/components/GameDetails/providers";
import { useWebpSupport } from "@/v2/composables/useWebpSupport";
import { collectionCoverList } from "@/v2/utils/collectionCovers";

defineOptions({ inheritAttrs: false });

const props = defineProps<{
  rom: DetailedRom;
  summary: string | null | undefined;
  sections: InfoGridSection[];
  playerCount: string | null;
  userCollections: UserCollectionSchema[];
  hltb: RomHLTBMetadata | null | undefined;
  lastPlayed: string | null;
  screenshots: string[];
  expansions: IGDBRelatedGame[];
  dlcs: IGDBRelatedGame[];
  remakes: IGDBRelatedGame[];
  remasters: IGDBRelatedGame[];
  similarGames: IGDBRelatedGame[];
}>();

const hasAgeRatings = computed(
  () => (props.rom.metadatum?.age_ratings?.length ?? 0) > 0,
);
const hasQuickFacts = computed(
  () => !!props.playerCount || hasAgeRatings.value,
);

// Mirror HLTBStrip's "has anything to show" so the section heading only
// appears alongside the strip (which renders nothing without durations).
const hasHltb = computed(() => {
  const m = props.hltb;
  if (!m) return false;
  return [m.main_story, m.main_plus_extra, m.completionist, m.all_styles].some(
    (v) => (v ?? 0) > 0,
  );
});

// Enrich the slim `{ id, name }` user_collections payload from the
// ROM with the full Collection record (cover paths, rom_count) the
// store already holds — so we can render real CollectionTile mosaics
// instead of stripped chips. Falls back to a bare entry if the store
// is empty (e.g. deep-link before the AppLayout fetch resolves).
const { t } = useI18n();
const collectionsStore = storeCollections();
const { toWebp } = useWebpSupport();

type CollectionTileEntry = {
  id: number;
  name: string;
  rom_count: number;
  covers: string[];
  link: string;
};

const userCollectionTiles = computed<CollectionTileEntry[]>(() =>
  props.userCollections.map((c) => {
    const full = collectionsStore.getCollection(c.id);
    return {
      id: c.id,
      name: full?.name ?? c.name,
      rom_count: full?.rom_count ?? 0,
      covers: full ? collectionCoverList(full, toWebp) : [],
      link: `/collection/${c.id}`,
    };
  }),
);

// Related — show the panel only if at least one section has items.
const hasRelated = computed(
  () =>
    props.expansions.length +
      props.dlcs.length +
      props.remakes.length +
      props.remasters.length +
      props.similarGames.length >
    0,
);

// Attribution — credit the metadata providers that supplied data for this
// ROM (mirrors v1's GameInfo footer). Reuses the PROVIDERS registry so the
// list stays in sync with the Metadata tab; providers without a public URL
// render as plain text.
const dataProviders = computed(() =>
  PROVIDERS.map((p) => {
    const id = providerId(props.rom, p);
    if (id === null) return null;
    return { name: p.name, href: p.url ? p.url(id) : null };
  }).filter((e): e is { name: string; href: string | null } => e !== null),
);

// Cover art is credited from the cover URL's host (covers can come from
// sources that aren't in PROVIDERS, e.g. SteamGridDB / Libretro).
const COVER_HOSTS: Record<string, string> = {
  "images.igdb.com": "IGDB",
  "screenscraper.fr": "ScreenScraper",
  "neoclone.screenscraper.fr": "ScreenScraper",
  "cdn.mobygames.com": "MobyGames",
  "cdn2.mobygames.com": "MobyGames",
  "retroachievements.org": "RetroAchievements",
  "media.retroachievements.org": "RetroAchievements",
  "images.launchbox-app.com": "LaunchBox",
  "cdn.steamgriddb.com": "SteamGridDB",
  "cdn2.steamgriddb.com": "SteamGridDB",
  "hasheous.org": "Hasheous",
  "infinity.unstable.life": "Flashpoint",
  "howlongtobeat.com": "HowLongToBeat",
  "thumbnails.libretro.com": "Libretro",
};

const coverSource = computed(() => {
  if (!props.rom.url_cover) return null;
  try {
    return COVER_HOSTS[new URL(props.rom.url_cover).hostname] ?? null;
  } catch {
    return null;
  }
});
</script>

<template>
  <section class="overview-tab">
    <!-- 1. Summary -->
    <p v-if="summary" class="overview-tab__summary">{{ summary }}</p>

    <!-- 2. Per-ROM fact rows (left-labelled). Last played + the
         per-game characteristics — Players, Age rating, RomM
         collections — get a row each so each fact can render its own
         semantic widget instead of being flattened to a chip list. -->
    <div
      v-if="lastPlayed || hasQuickFacts || userCollectionTiles.length"
      class="overview-tab__facts"
    >
      <div v-if="lastPlayed" class="overview-tab__row">
        <div class="overview-tab__label">{{ t("rom.last-played") }}</div>
        <div class="overview-tab__field">{{ lastPlayed }}</div>
      </div>

      <div v-if="playerCount" class="overview-tab__row">
        <div class="overview-tab__label">{{ t("rom.player-count") }}</div>
        <div class="overview-tab__field">
          <PlayerCountBadge :value="playerCount" />
        </div>
      </div>

      <div v-if="hasAgeRatings" class="overview-tab__row">
        <div class="overview-tab__label">{{ t("rom.age-rating") }}</div>
        <div class="overview-tab__field">
          <AgeRatingBadges :rom="rom" />
        </div>
      </div>

      <div
        v-if="userCollectionTiles.length"
        class="overview-tab__row overview-tab__row--tiles"
      >
        <div class="overview-tab__label">{{ t("rom.collections") }}</div>
        <div class="overview-tab__field overview-tab__field--scroll-x">
          <CollectionTile
            v-for="c in userCollectionTiles"
            :id="c.id"
            :key="c.id"
            :to="c.link"
            :name="c.name"
            :rom-count="c.rom_count"
            :covers="c.covers"
            kind="regular"
            variant="row"
          />
        </div>
      </div>
    </div>

    <!-- 3. Info grid -->
    <InfoGrid :sections="sections" />

    <!-- 4. Screenshots — scraped metadata images, read-only here. -->
    <div v-if="screenshots.length" class="overview-tab__section">
      <h4 class="overview-tab__section-heading">
        <RIcon icon="mdi-image-multiple-outline" size="14" />
        {{ t("rom.screenshots") }}
      </h4>
      <ScreenshotsTab :screenshots="screenshots.map((url) => ({ url }))" />
    </div>

    <!-- 5. HLTB -->
    <div v-if="hasHltb" class="overview-tab__section">
      <h4 class="overview-tab__section-heading">
        <RIcon icon="mdi-clock-outline" size="14" />
        {{ t("rom.how-long-to-beat") }}
      </h4>
      <HLTBStrip :metadata="hltb" />
    </div>

    <!-- 5. Related games — each category gets its own labelled section,
         rendered inline as siblings to the rest of the overview blocks.
         No collapsible wrapper: these sections aren't a distinct
         "surface" the user needs to expand into; they're just more
         metadata, and the empty sections are already hidden by their
         own `v-if`. -->
    <template v-if="hasRelated">
      <div v-if="expansions.length" class="overview-tab__section">
        <h4 class="overview-tab__section-heading">
          <RIcon icon="mdi-puzzle-outline" size="14" />
          Expansions
        </h4>
        <RelatedGamesGrid title="" :items="expansions" />
      </div>
      <div v-if="dlcs.length" class="overview-tab__section">
        <h4 class="overview-tab__section-heading">
          <RIcon icon="mdi-package-variant-closed" size="14" />
          DLC
        </h4>
        <RelatedGamesGrid title="" :items="dlcs" />
      </div>
      <div v-if="remakes.length" class="overview-tab__section">
        <h4 class="overview-tab__section-heading">
          <RIcon icon="mdi-refresh" size="14" />
          Remakes
        </h4>
        <RelatedGamesGrid title="" :items="remakes" />
      </div>
      <div v-if="remasters.length" class="overview-tab__section">
        <h4 class="overview-tab__section-heading">
          <RIcon icon="mdi-image-auto-adjust" size="14" />
          Remasters
        </h4>
        <RelatedGamesGrid title="" :items="remasters" />
      </div>
      <div v-if="similarGames.length" class="overview-tab__section">
        <h4 class="overview-tab__section-heading">
          <RIcon icon="mdi-shape-outline" size="14" />
          Similar games
        </h4>
        <RelatedGamesGrid title="" :items="similarGames" />
      </div>
    </template>

    <!-- 6. Attribution — credit the metadata + cover-art sources -->
    <div
      v-if="dataProviders.length || coverSource"
      class="overview-tab__attribution"
    >
      <i18n-t
        v-if="dataProviders.length"
        keypath="rom.data-provided-by"
        tag="div"
      >
        <template #sources>
          <template v-for="(source, index) in dataProviders" :key="source.name"
            ><span v-if="index > 0">{{
              index === dataProviders.length - 1 ? ` ${t("common.and")} ` : ", "
            }}</span
            ><a
              v-if="source.href"
              class="overview-tab__attribution-link"
              :href="source.href"
              target="_blank"
              rel="noopener"
              >{{ source.name }}</a
            ><span v-else>{{ source.name }}</span></template
          >
        </template>
      </i18n-t>
      <i18n-t
        v-if="coverSource && rom.url_cover"
        keypath="rom.cover-art-provided-by"
        tag="div"
      >
        <template #source>
          <a
            class="overview-tab__attribution-link"
            :href="rom.url_cover"
            target="_blank"
            rel="noopener"
            >{{ coverSource }}</a
          >
        </template>
      </i18n-t>
    </div>
  </section>
</template>

<style scoped>
.overview-tab {
  display: flex;
  flex-direction: column;
  gap: 30px;
}

.overview-tab__summary {
  font-size: 13.5px;
  line-height: 1.7;
  color: var(--r-color-fg-secondary);
  margin: 0;
}
.overview-tab__summary--muted {
  font-style: italic;
  color: var(--r-color-fg-muted);
}

/* Left-labelled fact rows. Each row pairs a 120-px uppercase eyebrow
   label with a content cell on the right, so single-value widgets
   (Last played, Players badge, Age rating badges, RomM collections)
   stay aligned in a column without forcing every row through the
   InfoGrid chip styling. */
.overview-tab__facts {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.overview-tab__row {
  display: flex;
  align-items: center;
  gap: 16px;
}
.overview-tab__label {
  width: 120px;
  flex-shrink: 0;
  font-size: 10.5px;
  font-weight: var(--r-font-weight-bold);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--r-color-fg-faint);
}
.overview-tab__field {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 12px;
}
.overview-tab__field--chips {
  flex-wrap: wrap;
  gap: 6px;
}
.overview-tab__muted {
  color: var(--r-color-fg-faint);
  font-style: italic;
}

/* Tile-row variant — the eyebrow pins to the top of the tile column
   (instead of centring through the ~190px-tall CollectionTile) so the
   label hovers over the mosaic rather than drifting halfway down it.
   Vertical padding on the scroll container gives the hover-pop
   (CollectionTile's scale + elevated shadow) room to render
   before the scroll container clips it — `overflow-x: auto` also
   clips on Y per the CSS spec, so without this the shadow and
   lifted edge get sheared off. */
.overview-tab__row--tiles {
  align-items: flex-start;
}
.overview-tab__row--tiles .overview-tab__label {
  padding-top: 8px;
}
.overview-tab__field--scroll-x {
  flex-wrap: nowrap;
  gap: 18px;
  padding: 6px 4px 10px;
  overflow-x: auto;
  scrollbar-width: thin;
  scrollbar-color: var(--r-color-border-strong) transparent;
}
.overview-tab__field--scroll-x::-webkit-scrollbar {
  height: 6px;
}
.overview-tab__field--scroll-x::-webkit-scrollbar-thumb {
  background: var(--r-color-border-strong);
  border-radius: 3px;
}

/* Labelled overview section (screenshots, HLTB, each related-games
   category) — a heading + its content as a sibling block in the overview
   flex column; the outer column's `gap: 30px` provides separation. */
.overview-tab__section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.overview-tab__section-heading {
  margin: 0;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  font-weight: var(--r-font-weight-bold);
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--r-color-fg-faint);
}

/* Attribution — a quiet, italic credits footer for the metadata and
   cover-art sources. */
.overview-tab__attribution {
  display: flex;
  flex-direction: column;
  gap: 2px;
  font-size: 11.5px;
  font-style: italic;
  line-height: 1.6;
  color: var(--r-color-fg-faint);
}
.overview-tab__attribution-link {
  color: inherit;
  text-decoration: underline;
  text-decoration-color: var(--r-color-border-strong);
  text-underline-offset: 2px;
  transition: color var(--r-motion-fast) var(--r-motion-ease-out);
}
.overview-tab__attribution-link:hover {
  color: var(--r-color-fg-secondary);
}
</style>
