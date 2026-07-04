<script setup lang="ts">
// Platform view — owns the platform-specific load flow (route param →
// ensure platforms loaded → setCurrentPlatform → fetch metadata) and
// the three-tab surface that sits above the gallery:
//   • Library  — the gallery (delegated to `GalleryShell`).
//   • Firmware — `FirmwareTab` (upload / download / delete firmware).
//   • Settings — `SettingsTab` (details + cover-style picker).
//
// Layout choice: `PlatformHead` (InfoPanel + RTabNav) lives INSIDE the
// scrolling container of whichever branch is active. On Library, it
// rides in `GalleryShell`'s `#header` slot so it scrolls away with
// the cards and the toolbar pins below it — the same vocabulary the
// pre-tabs gallery had. On Firmware / Settings it sits in a plain
// scroll wrapper above the tab body, so the user gets a single
// natural scroll for the whole page.
//
// Action ribbon (Upload / Scan) lives inside the head component;
// Edit (custom_name) and Delete moved inline into the Settings tab.
import { RDivider, type RTabNavItem } from "@v2/lib";
import { storeToRefs } from "pinia";
import { computed, nextTick, onMounted, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { onBeforeRouteUpdate, useRoute, useRouter } from "vue-router";
import { ROUTES } from "@/plugins/router";
import platformApi from "@/services/api/platform";
import romApi from "@/services/api/rom";
import storePlatforms, { type Platform } from "@/stores/platforms";
import { formatBytes } from "@/utils";
import FirmwareTab from "@/v2/components/Gallery/FirmwareTab.vue";
import GalleryShell from "@/v2/components/Gallery/GalleryShell.vue";
import PlatformHead from "@/v2/components/Gallery/PlatformHead.vue";
import ScanPlatformDialog from "@/v2/components/Gallery/ScanPlatformDialog.vue";
import SettingsTab from "@/v2/components/Gallery/SettingsTab.vue";
import { useCan } from "@/v2/composables/useCan";
import { useConfirm } from "@/v2/composables/useConfirm";
import { useSnackbar } from "@/v2/composables/useSnackbar";
import storeGalleryRoms from "@/v2/stores/galleryRoms";

const { t } = useI18n();
const route = useRoute();
const router = useRouter();
const platformsStore = storePlatforms();
const galleryRoms = storeGalleryRoms();
const snackbar = useSnackbar();
const confirm = useConfirm();
const { currentPlatform, total, romIdIndex } = storeToRefs(galleryRoms);

const notFound = ref(false);
const shellRef = ref<InstanceType<typeof GalleryShell> | null>(null);
const deleting = ref(false);
const scanOpen = ref(false);
const randomLoading = ref(false);

// Permissions — `useCan` is reactive against the grants store, so the
// ribbon buttons hide automatically when the user's role changes.
const canEditPlatform = useCan("platform.edit");
const canScan = useCan("library.scan");
const canDownload = useCan("rom.download");

// ── Tabs ─────────────────────────────────────────────────────────
// URL-persistent via `?tab=` (mirrors the GameDetails pattern). The
// default tab is `library`.
type TabId = "library" | "firmware" | "settings";
const VALID_TABS = new Set<TabId>(["library", "firmware", "settings"]);

function parseTab(v: unknown): TabId {
  return typeof v === "string" && VALID_TABS.has(v as TabId)
    ? (v as TabId)
    : "library";
}

const tab = ref<TabId>(parseTab(route.query.tab));
watch(tab, (value) => {
  if (route.query.tab !== value) {
    router.replace({
      path: route.path,
      query: { ...route.query, tab: value },
    });
  }
});
watch(
  () => route.query.tab,
  (value) => {
    const next = parseTab(value);
    if (next !== tab.value) tab.value = next;
  },
);

const tabs = computed<RTabNavItem[]>(() => [
  { id: "library", label: t("common.library") },
  { id: "firmware", label: t("platform.firmware-bios") },
  { id: "settings", label: t("platform.settings") },
]);

const headLabels = computed(() => ({
  upload: t("platform.upload-roms"),
  scan: t("platform.scan-platform"),
  random: t("platform.random-rom"),
  download: t("platform.download-platform"),
}));

function onTabChange(next: string) {
  tab.value = next as TabId;
}

const tags = computed<string[]>(() => {
  const p = currentPlatform.value;
  if (!p) return [];
  const out: string[] = [];
  if (p.category) out.push(p.category);
  if (p.family_name) out.push(p.family_name);
  if (p.generation && p.generation > 0)
    out.push(t("rom.generation-n", { n: p.generation }));
  return out;
});

type StatRow = { label: string; value: string };
const platformStats = computed<StatRow[]>(() => {
  const p = currentPlatform.value;
  if (!p) return [];
  const rows: StatRow[] = [
    {
      label: t("platform.in-library"),
      value: String(p.rom_count ?? total.value),
    },
    { label: t("platform.on-disk"), value: formatBytes(p.fs_size_bytes ?? 0) },
  ];
  if (p.firmware_count) {
    rows.push({
      label: t("common.firmware"),
      value: String(p.firmware_count),
    });
  }
  return rows;
});

// External metadata-provider chips. Each entry knows how to derive its
// label + outbound URL from the platform; the chip is only rendered
// when the ID exists. v2 surface — moved inline from v1's
// PlatformInfoDrawer so users get the providers at a glance without
// opening any flyout.
interface ProviderChip {
  key: string;
  label: string;
  href: string | null;
  asset: string;
  title?: string;
}

const providerChips = computed<ProviderChip[]>(() => {
  const p = currentPlatform.value;
  if (!p) return [];
  const out: ProviderChip[] = [];
  if (p.igdb_id != null) {
    out.push({
      key: "igdb",
      label: String(p.igdb_id),
      href: `https://www.igdb.com/platforms/${p.igdb_slug}`,
      asset: "/assets/scrappers/igdb.png",
      title: "IGDB",
    });
  }
  if (p.ss_id != null) {
    out.push({
      key: "ss",
      label: String(p.ss_id),
      href: `https://www.screenscraper.fr/gamesinfos.php?plateforme=${p.ss_id}`,
      asset: "/assets/scrappers/ss.png",
      title: "ScreenScraper",
    });
  }
  if (p.moby_slug != null) {
    out.push({
      key: "moby",
      label: p.moby_id != null ? String(p.moby_id) : p.moby_slug,
      href: `https://www.mobygames.com/platform/${p.moby_slug}`,
      asset: "/assets/scrappers/moby.png",
      title: "MobyGames",
    });
  }
  if (p.ra_id != null) {
    out.push({
      key: "ra",
      label: String(p.ra_id),
      href: `https://retroachievements.org/system/${p.ra_id}/games`,
      asset: "/assets/scrappers/ra.png",
      title: "RetroAchievements",
    });
  }
  if (p.launchbox_id != null) {
    out.push({
      key: "launchbox",
      label: String(p.launchbox_id),
      href: `https://gamesdb.launchbox-app.com/platforms/games/${p.launchbox_id}`,
      asset: "/assets/scrappers/launchbox.png",
      title: "LaunchBox",
    });
  }
  if (p.hasheous_id != null) {
    out.push({
      key: "hasheous",
      label: String(p.hasheous_id),
      href: `https://hasheous.org/index.html?page=dataobjectdetail&type=platform&id=${p.hasheous_id}`,
      asset: "/assets/scrappers/hasheous.png",
      title: "Hasheous",
    });
  }
  if (p.tgdb_id != null) {
    out.push({
      key: "tgdb",
      label: String(p.tgdb_id),
      href: `https://thegamesdb.net/platform.php?id=${p.tgdb_id}`,
      asset: "/assets/scrappers/tgdb.png",
      title: "TheGamesDB",
    });
  }
  if (p.flashpoint_id != null) {
    out.push({
      key: "flashpoint",
      label: "",
      href: null,
      asset: "/assets/scrappers/flashpoint.png",
      title: "Flashpoint",
    });
  }
  if (p.hltb_slug != null) {
    out.push({
      key: "hltb",
      label: "",
      href: null,
      asset: "/assets/scrappers/hltb.png",
      title: "HowLongToBeat",
    });
  }
  if (p.libretro_slug != null) {
    out.push({
      key: "libretro",
      label: "",
      href: null,
      asset: "/assets/scrappers/libretro.png",
      title: "Libretro",
    });
  }
  return out;
});

async function ensurePlatforms() {
  if (platformsStore.allPlatforms.length === 0) {
    await platformsStore.fetchPlatforms();
  }
}

async function loadForId(platformId: number) {
  await ensurePlatforms();
  const cached = platformsStore.allPlatforms.find((p) => p.id === platformId);
  if (!cached) {
    notFound.value = true;
    return;
  }
  notFound.value = false;
  if (currentPlatform.value?.id !== cached.id) {
    galleryRoms.resetGallery();
    galleryRoms.setCurrentPlatform(cached);
  }
  document.title = cached.display_name;
  // Bootstrap metadata only; grid (shell viewport-sync) and list
  // (GameListRow's onMounted) both hydrate rows per-position from here.
  await galleryRoms.fetchInitialMetadata();
  await nextTick();
  shellRef.value?.applyRestoredScroll();
  // Refresh the platform record in the background so the Firmware
  // and Settings tabs see the live state (firmware list, fs_size,
  // verification flags). The cached `allPlatforms` only holds what
  // `/platforms` returned on first load; firmware uploaded from other
  // sessions or other surfaces would otherwise look empty here.
  try {
    const { data: fresh } = await platformApi.getPlatform(platformId);
    if (fresh) {
      platformsStore.update(fresh);
      if (galleryRoms.currentPlatform?.id === fresh.id) {
        galleryRoms.setCurrentPlatform(fresh);
      }
    }
  } catch {
    // Non-fatal — the cached snapshot stays in place, and the tabs
    // surface what's already known. Logged by the axios interceptor.
  }
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

// ── Admin actions ───────────────────────────────────────────────
function onUploadRoms() {
  const p = currentPlatform.value;
  if (!p) return;
  router.push({ name: ROUTES.UPLOAD, query: { platform: String(p.id) } });
}

function onScan() {
  if (!currentPlatform.value) return;
  scanOpen.value = true;
}

// Random ROM — pick one game from this platform and jump to its
// details. Mirrors the Home RandomPickWidget approach: a cheap
// count-only fetch gives the `total`, then a single-item fetch at a
// random offset resolves the ROM. Scoped to the current platform via
// `platformIds`.
async function onRandomGame() {
  const p = currentPlatform.value;
  if (!p || randomLoading.value) return;
  randomLoading.value = true;
  try {
    const { data: head } = await romApi.getRoms({
      platformIds: [p.id],
      limit: 1,
      offset: 0,
    });
    if (!head.total) {
      snackbar.info(t("platform.random-rom-empty"));
      return;
    }
    const randomOffset = Math.floor(Math.random() * head.total);
    const { data } = await romApi.getRoms({
      platformIds: [p.id],
      limit: 1,
      offset: randomOffset,
    });
    const pick = data.items[0];
    if (!pick) {
      snackbar.info(t("platform.random-rom-empty"));
      return;
    }
    router.push({ name: ROUTES.ROM, params: { rom: pick.id } });
  } catch {
    snackbar.error(t("platform.random-rom-error"));
  } finally {
    randomLoading.value = false;
  }
}

// Download all — `romIdIndex` already holds every matching ROM ID for
// this platform (the gallery store populates it on load), so hand that
// straight to the zip download without a second fetch.
function onDownload() {
  const p = currentPlatform.value;
  const romIDs = romIdIndex.value;
  if (!p || romIDs.length === 0) return;
  void romApi.bulkDownloadRoms({ romIDs, filename: `${p.display_name}.zip` });
  snackbar.info(t("gallery.selection-download-many", { n: romIDs.length }));
}

async function onDelete() {
  const p = currentPlatform.value;
  if (!p) return;
  const ok = await confirm({
    title: t("platform.delete-platform", "Delete platform"),
    body: `This removes "${p.display_name}" from RomM along with its database entries (${p.rom_count} ROMs). ROM files on disk are NOT deleted.`,
    confirmText: t("platform.delete-platform", "Delete platform"),
    tone: "danger",
    requireTyped: p.display_name,
  });
  if (!ok) return;

  deleting.value = true;
  try {
    await platformApi.deletePlatform({ platform: p as Platform });
    platformsStore.remove(p as Platform);
    snackbar.success(`Platform "${p.display_name}" deleted`, {
      icon: "mdi-check-bold",
    });
    router.push({ name: ROUTES.PLATFORMS_INDEX });
  } catch (err) {
    const e = err as {
      response?: { data?: { msg?: string } };
      message?: string;
    };
    snackbar.error(
      `Failed to delete platform: ${
        e?.response?.data?.msg || e?.message || "unknown error"
      }`,
      { icon: "mdi-close-circle" },
    );
  } finally {
    deleting.value = false;
  }
}
</script>

<template>
  <!-- LIBRARY — full GalleryShell with PlatformHead in #header so the
       head band scrolls naturally with the cards and the toolbar pins
       below it. Same scroll vocabulary as the pre-tabs gallery. -->
  <GalleryShell
    v-if="tab === 'library'"
    ref="shellRef"
    :has-header="!!currentPlatform"
    :search-placeholder="'Filter this platform…'"
    empty-message="No games in this platform yet."
    :not-found="notFound"
    not-found-message="Platform not found."
    :show-platform-badge="false"
    :show-platforms-in-filter="false"
    :show-platform-column="false"
    :skeleton-row-count="4"
  >
    <template #header>
      <PlatformHead
        v-if="currentPlatform"
        :platform="currentPlatform"
        :tab="tab"
        :tabs="tabs"
        :tags="tags"
        :stats="platformStats"
        :providers="providerChips"
        :can-edit="canEditPlatform"
        :can-scan="canScan"
        :can-download="canDownload"
        :random-loading="randomLoading"
        :labels="headLabels"
        @update:tab="onTabChange"
        @upload="onUploadRoms"
        @scan="onScan"
        @random="onRandomGame"
        @download="onDownload"
      />
    </template>
  </GalleryShell>

  <!-- FIRMWARE / SETTINGS — plain scroll wrapper that hosts the same
       PlatformHead above the tab body. Whole page scrolls together so
       the user keeps the head band, the divider, and the tab content
       in one natural scroll surface. -->
  <section v-else class="r-v2-plat-tabs">
    <div class="r-v2-plat-tabs__scroll">
      <PlatformHead
        v-if="currentPlatform"
        :platform="currentPlatform"
        :tab="tab"
        :tabs="tabs"
        :tags="tags"
        :stats="platformStats"
        :providers="providerChips"
        :can-edit="canEditPlatform"
        :can-scan="canScan"
        :can-download="canDownload"
        :random-loading="randomLoading"
        :labels="headLabels"
        @update:tab="onTabChange"
        @upload="onUploadRoms"
        @scan="onScan"
        @random="onRandomGame"
        @download="onDownload"
      />
      <RDivider class="r-v2-plat-tabs__divider" />
      <div v-if="currentPlatform" class="r-v2-plat-tabs__panel">
        <FirmwareTab v-if="tab === 'firmware'" :platform="currentPlatform" />
        <SettingsTab
          v-else-if="tab === 'settings'"
          :platform="currentPlatform"
          :deleting="deleting"
          @delete="onDelete"
        />
      </div>
    </div>
  </section>

  <!-- Per-platform scan dialog — mounted at the view level so it
       survives tab switches without remounting. Gates on `currentPlatform`
       so we never pass a `null` to the dialog body. -->
  <ScanPlatformDialog
    v-if="currentPlatform"
    v-model="scanOpen"
    :platform="currentPlatform"
  />
</template>

<style scoped>
/* Firmware / Settings branch — single scroll wrapper that owns the
   page scroll. The PlatformHead and the tab body scroll together as
   one surface, so the user gets the same natural scroll feel as the
   Library tab (where GalleryShell handles it). */
.r-v2-plat-tabs {
  /* `dvh` (not `vh`) so the section matches the mobile visible viewport
     instead of the larger address-bar-hidden one — otherwise it spills below
     the fold and stacks a second, document-level scroll on the internal one
     ("double scroll"). Same rationale as GalleryShell / IndexShell. */
  height: calc(100vh - var(--r-nav-h));
  height: calc(100dvh - var(--r-nav-h));
  overflow: hidden;
  position: relative;
}
/* On sm-and-down the layout <main> reserves the bottom tab bar's height; this
   full-height section would otherwise sit on top of that padding and push the
   document past one viewport. Cancel it with a matching negative margin so the
   section extends under the (translucent) bar with a single scroll — the inner
   scroll's bottom spacer lifts the last content (danger zone) clear of it. */
html[data-bp~="sm-and-down"] .r-v2-plat-tabs {
  margin-bottom: calc(
    -1 * (var(--r-bottom-nav-h) + env(safe-area-inset-bottom))
  );
}

.r-v2-plat-tabs__scroll {
  height: 100%;
  overflow-y: auto;
  padding: 32px var(--r-row-pad) 60px;
}
html[data-bp~="sm-and-down"] .r-v2-plat-tabs__scroll {
  padding-bottom: calc(
    var(--r-bottom-nav-h) + env(safe-area-inset-bottom) + 24px
  );
}

.r-v2-plat-tabs__divider {
  margin: 0 0 24px;
}

.r-v2-plat-tabs__panel {
  /* Tab body — Firmware / Settings render their own internal layouts
     (lists, two-column grids). The wrapper just provides breathing
     room and stops the inner content from running edge-to-edge with
     the head's icon column. */
  min-height: 0;
}
</style>
