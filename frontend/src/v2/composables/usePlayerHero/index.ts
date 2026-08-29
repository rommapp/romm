// usePlayerHero — the seed / hero / title block a v2 player view opens with.
// EmulatorJS and Ruffle both refetch the full ROM on mount but need a cover in
// the DOM *before* that resolves, so the shared-element morph from the gallery
// or details cover pairs on entry.
//
// Seeding is synchronous: from GameDetails the full DetailedRom is already in
// `currentRom`; on a direct gallery→play only a SimpleRom exists, so a
// cover-only `heroSeed` stands in until the view's own fetch lands.
//
// The caller owns the `rom` ref — EmulatorJS needs a deep one for the save and
// state lists it mutates — and this seeds into it.
import { computed, type ComputedRef, type Ref, shallowRef, watch } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute } from "vue-router";
import storeRoms, { type DetailedRom, type SimpleRom } from "@/stores/roms";
import { useBackgroundArt } from "@/v2/composables/useBackgroundArt";
import { usePageTitle } from "@/v2/composables/usePageTitle";
import storeGalleryRoms from "@/v2/stores/galleryRoms";

export function usePlayerHero(rom: Ref<DetailedRom | null>): {
  romId: number;
  heroSeed: Ref<SimpleRom | null>;
  heroRom: ComputedRef<DetailedRom | SimpleRom | null>;
  title: ComputedRef<string>;
  platformLabel: ComputedRef<string>;
} {
  const { t } = useI18n();
  const route = useRoute();
  const setBgArt = useBackgroundArt();

  const romId = Number(route.params.rom);

  const seededRom = storeRoms().currentRom;
  if (seededRom?.id === romId) {
    rom.value = seededRom;
  }
  const heroSeed = shallowRef<SimpleRom | null>(null);
  if (!rom.value) {
    heroSeed.value = storeGalleryRoms().getRomById(romId);
  }

  const heroRom = computed<DetailedRom | SimpleRom | null>(
    () => rom.value ?? heroSeed.value,
  );

  const title = computed(
    () => heroRom.value?.name || heroRom.value?.fs_name_no_ext || "",
  );

  usePageTitle(() =>
    title.value ? t("play.page-title", { name: title.value }) : null,
  );

  const platformLabel = computed(
    () =>
      heroRom.value?.platform_custom_name ||
      heroRom.value?.platform_display_name ||
      "",
  );

  // Background art keeps the plain 2D cover — a blurred disc or cartridge
  // reads poorly as a full-bleed backdrop.
  watch(
    () => {
      const r = rom.value;
      if (!r) return null;
      return r.path_cover_large ?? r.path_cover_small ?? r.url_cover ?? null;
    },
    (url) => {
      if (url) setBgArt(url);
    },
    { immediate: true },
  );

  return { romId, heroSeed, heroRom, title, platformLabel };
}
