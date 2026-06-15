<script setup lang="ts">
// RelatedGameCard — single card in the related-games strip.
//
// Reuses the gallery's GameCard in `static` mode so the cover art,
// hover-lift, label-truncation and tooltip-on-hover read identically
// to every other game cover in the app. The action overlay, rating
// chip, status badge, platform icon and gallery-selection chrome are
// all suppressed by `static + showPlatformIcon=false` — we only want
// "a tile that looks like a game".
//
// IGDB → RomM cross-reference (per v1's
// `frontend/src/components/common/Game/Card/Related.vue`): on mount
// the card asks the backend whether the IGDB id resolves to a local
// ROM. If it does, the click jumps to the internal detail page via
// the router; otherwise the click opens the IGDB game page in a new
// tab so the user can still reach metadata for games they don't own.
import { RIcon } from "@v2/lib";
import { computed, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useRouter } from "vue-router";
import type {
  IGDBRelatedGame,
  RomMetadataSchema,
  RomUserSchema,
} from "@/__generated__";
import romApi from "@/services/api/rom";
import type { SimpleRom } from "@/stores/roms";
import GameCard from "@/v2/components/GameCard/GameCard.vue";

defineOptions({ inheritAttrs: false });

const props = defineProps<{ game: IGDBRelatedGame }>();

const { t } = useI18n();
const router = useRouter();
const romId = ref<number | null>(null);
const inLibrary = computed(() => romId.value !== null);

onMounted(async () => {
  try {
    const res = await romApi.getRomByMetadataProvider({
      field: "igdb_id",
      id: props.game.id,
    });
    romId.value = res.data.id;
  } catch {
    // Stay on the IGDB external fallback — game isn't in the local
    // library or the endpoint denied the lookup.
  }
});

// Minimal SimpleRom satisfying the GameCard prop contract. id=0 marks
// it as synthetic — GameCard skips view-transition wiring and the
// router-link href. `static + showPlatformIcon=false` means every
// other field that could read off the rom is gated behind a v-if and
// never accessed, so the empty defaults are safe.
const EMPTY_METADATA: RomMetadataSchema = {
  rom_id: 0,
  genres: [],
  franchises: [],
  collections: [],
  companies: [],
  game_modes: [],
  age_ratings: [],
  player_count: "",
  first_release_date: null,
  average_rating: null,
};
const EMPTY_USER: RomUserSchema = {
  id: 0,
  user_id: 0,
  rom_id: 0,
  created_at: "",
  updated_at: "",
  last_played: null,
  is_main_sibling: false,
  backlogged: false,
  now_playing: false,
  hidden: false,
  rating: 0,
  difficulty: 0,
  completion: 0,
  status: null,
};

const syntheticRom = computed<SimpleRom>(() => ({
  id: 0,
  igdb_id: props.game.id,
  sgdb_id: null,
  moby_id: null,
  ss_id: null,
  ra_id: null,
  launchbox_id: null,
  hasheous_id: null,
  tgdb_id: null,
  flashpoint_id: null,
  hltb_id: null,
  gamelist_id: null,
  libretro_id: null,
  platform_id: 0,
  platform_slug: "",
  platform_fs_slug: "",
  platform_custom_name: null,
  platform_display_name: "",
  fs_name: props.game.name,
  fs_name_no_tags: props.game.name,
  fs_name_no_ext: props.game.name,
  fs_extension: "",
  fs_path: "",
  fs_size_bytes: 0,
  name: props.game.name,
  slug: props.game.slug,
  summary: null,
  alternative_names: [],
  youtube_video_id: null,
  metadatum: EMPTY_METADATA,
  igdb_metadata: null,
  moby_metadata: null,
  ss_metadata: null,
  launchbox_metadata: null,
  hasheous_metadata: null,
  flashpoint_metadata: null,
  hltb_metadata: null,
  gamelist_metadata: null,
  manual_metadata: null,
  path_cover_small: null,
  path_cover_large: null,
  url_cover: props.game.cover_url ?? null,
  has_manual: false,
  has_manual_files: false,
  has_soundtrack: false,
  path_manual: null,
  url_manual: null,
  path_video: null,
  is_unidentified: false,
  is_identified: false,
  revision: null,
  regions: [],
  languages: [],
  tags: [],
  crc_hash: null,
  md5_hash: null,
  sha1_hash: null,
  ra_hash: null,
  has_simple_single_file: false,
  has_nested_single_file: false,
  has_multiple_files: false,
  full_path: "",
  created_at: "",
  updated_at: "",
  missing_from_fs: false,
  has_notes: false,
  files: [],
  sibling_roms: [],
  rom_user: EMPTY_USER,
  merged_screenshots: [],
  merged_ra_metadata: null,
}));

// Static-mode GameCard emits @click for the consumer. Resolve the
// destination based on the IGDB → RomM lookup result.
function onClick(e: MouseEvent) {
  if (inLibrary.value) {
    void router.push(`/rom/${romId.value}`);
    return;
  }
  // Open the IGDB external link in a new tab — preserves the current
  // ROM's detail view so the user doesn't lose context.
  const url = `https://www.igdb.com/games/${props.game.slug}`;
  window.open(url, "_blank", "noopener,noreferrer");
  // The static-mode keyboard activator (`onStaticKeydown`) hands us a
  // KeyboardEvent cast to MouseEvent — both go through the same path.
  void e;
}
</script>

<template>
  <GameCard
    :rom="syntheticRom"
    static
    :show-platform-icon="false"
    :cover-src="game.cover_url"
    @click="onClick"
  >
    <!-- "Owned" tag at the top of the cover — signals the game is
         already in the user's library. Mirrors the top-left chip
         pattern v1 used for the related-game `type` overlay (DLC /
         Remake / …) so the visual rhythm matches across the app. -->
    <template v-if="inLibrary" #overlay>
      <span class="related-card__owned">
        <RIcon icon="mdi-check" size="11" />
        {{ t("common.owned") }}
      </span>
    </template>
  </GameCard>
</template>

<style scoped>
/* GameCard's `#overlay` slot container is itself absolutely anchored
   top-right; we re-anchor it to the top-left so the "Owned" pill
   lives in the same corner v1's related-game `type` chip used to,
   keeping the visual rhythm consistent across the app. */
:deep(.r-gc__overlay-slot) {
  right: auto;
  left: 6px;
}

/* "Owned" pill — brand-tinted with a check glyph. Slight blur on the
   background so it composites cleanly over bright cover art. */
.related-card__owned {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 2px 7px 2px 5px;
  border-radius: var(--r-radius-chip);
  font-size: 9.5px;
  font-weight: var(--r-font-weight-bold);
  letter-spacing: 0.06em;
  text-transform: uppercase;
  background: var(--r-color-brand-primary);
  color: var(--r-color-overlay-fg);
  backdrop-filter: blur(4px);
  -webkit-backdrop-filter: blur(4px);
  box-shadow: 0 1px 4px color-mix(in srgb, black 45%, transparent);
}
</style>
