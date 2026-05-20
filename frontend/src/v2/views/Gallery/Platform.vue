<script setup lang="ts">
// Platform gallery — thin orchestrator around `GalleryShell`. Owns the
// platform-specific load flow (route param → ensure platforms loaded →
// setCurrentPlatform → fetchWindowAt(0)) and fills the shell's
// `#header` slot with an InfoPanel. Everything else (virtualizer,
// toolbar, AlphaStrip, dwell, scroll restoration, list mode) lives in
// the shell so any cross-view fix lands once for all three views.
//
// Admin entry point: a kebab `RMenu` in the InfoPanel's `#actions`
// slot exposes the actions that v1 surfaced through PlatformInfoDrawer
// (Scan / Delete / Settings…). Scan dispatches the socket event and
// flips `scanningStore.scanning`; Settings opens
// `PlatformSettingsDrawer` (details + cover style); Delete goes through
// `useConfirm` with a typed-confirm prompt and then
// `platformApi.deletePlatform`, then routes away on success.
import {
  RBtn,
  RChip,
  RDivider,
  RMenu,
  RMenuItem,
  RPlatformIcon,
} from "@v2/lib";
import { storeToRefs } from "pinia";
import { computed, nextTick, onMounted, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { onBeforeRouteUpdate, useRoute, useRouter } from "vue-router";
import { ROUTES } from "@/plugins/router";
import platformApi from "@/services/api/platform";
import socket from "@/services/socket";
import storeHeartbeat from "@/stores/heartbeat";
import storePlatforms, { type Platform } from "@/stores/platforms";
import storeScanning from "@/stores/scanning";
import { formatBytes } from "@/utils";
import FirmwareDrawer from "@/v2/components/Gallery/FirmwareDrawer.vue";
import GalleryShell from "@/v2/components/Gallery/GalleryShell.vue";
import InfoPanel from "@/v2/components/Gallery/InfoPanel.vue";
import PlatformSettingsDrawer from "@/v2/components/Gallery/PlatformSettingsDrawer.vue";
import Stat from "@/v2/components/shared/Stat.vue";
import { useCan } from "@/v2/composables/useCan";
import { useConfirm } from "@/v2/composables/useConfirm";
import { useSnackbar } from "@/v2/composables/useSnackbar";
import storeGalleryRoms from "@/v2/stores/galleryRoms";

const { t } = useI18n();
const route = useRoute();
const router = useRouter();
const platformsStore = storePlatforms();
const galleryRoms = storeGalleryRoms();
const scanningStore = storeScanning();
const heartbeatStore = storeHeartbeat();
const snackbar = useSnackbar();
const confirm = useConfirm();
const { currentPlatform, total } = storeToRefs(galleryRoms);
const { scanning } = storeToRefs(scanningStore);

const notFound = ref(false);
const shellRef = ref<InstanceType<typeof GalleryShell> | null>(null);
const settingsOpen = ref(false);
const firmwareOpen = ref(false);
const deleting = ref(false);

// Permissions — `useCan` is reactive against the grants store, so the
// menu items disable/hide automatically when the user's role changes.
const canEditPlatform = useCan("platform.edit");
const canDeletePlatform = useCan("platform.delete");
const canScan = useCan("library.scan");

const tags = computed<string[]>(() => {
  const p = currentPlatform.value;
  if (!p) return [];
  const out: string[] = [];
  if (p.category) out.push(p.category);
  if (p.family_name) out.push(p.family_name);
  if (p.generation && p.generation > 0) out.push(`Generation ${p.generation}`);
  return out;
});

type StatRow = { label: string; value: string };
const platformStats = computed<StatRow[]>(() => {
  const p = currentPlatform.value;
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

// ── Admin actions ───────────────────────────────────────────────
function onUploadRoms() {
  const p = currentPlatform.value;
  if (!p) return;
  router.push({ name: ROUTES.UPLOAD, query: { platform: String(p.id) } });
}

function onScan() {
  const p = currentPlatform.value;
  if (!p) return;
  scanningStore.setScanning(true);
  if (!socket.connected) socket.connect();
  socket.emit("scan", {
    platforms: [p.id],
    type: "quick",
    apis: heartbeatStore.getEnabledMetadataOptions().map((s) => s.value),
  });
  snackbar.info(`Scanning ${p.display_name}…`, {
    icon: "mdi-loading mdi-spin",
  });
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
    router.push({ name: "platforms" });
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
            v-for="tag in tags"
            :key="tag"
            size="small"
            variant="translucent"
            :rounded="20"
          >
            {{ tag }}
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
        <template v-if="providerChips.length" #providers>
          <a
            v-for="chip in providerChips"
            :key="chip.key"
            :href="chip.href ?? undefined"
            :target="chip.href ? '_blank' : undefined"
            rel="noopener noreferrer"
            :title="chip.title"
            class="r-v2-plat__provider"
            :class="{ 'r-v2-plat__provider--passive': !chip.href }"
          >
            <img
              :src="chip.asset"
              :alt="chip.title ?? chip.key"
              class="r-v2-plat__provider-logo"
            />
            <span v-if="chip.label" class="r-v2-plat__provider-label">
              {{ chip.label }}
            </span>
          </a>
        </template>

        <!-- Admin kebab — Scan / Settings / Firmware (placeholder) /
             Delete. Each item gates on its own `useCan` check; the
             menu itself stays visible so non-admins still see what
             the surface offers. -->
        <template #actions>
          <RMenu location="bottom end" :offset="6" width="220px">
            <template #activator="{ props: activatorProps }">
              <RBtn
                v-bind="activatorProps"
                variant="outlined"
                surface
                icon="mdi-dots-vertical"
                rounded="circle"
                aria-label="Platform actions"
              />
            </template>
            <RMenuItem
              v-if="canEditPlatform"
              :label="t('platform.upload-roms', 'Upload ROMs')"
              icon="mdi-cloud-upload-outline"
              @click="onUploadRoms"
            />
            <RMenuItem
              :label="t('scan.scan', 'Scan platform')"
              icon="mdi-magnify-scan"
              :disabled="!canScan || scanning"
              @click="onScan"
            />
            <RMenuItem
              :label="t('platform.firmware', 'Firmware')"
              icon="mdi-memory"
              @click="firmwareOpen = true"
            />
            <RMenuItem
              :label="t('platform.settings', 'Settings…')"
              icon="mdi-cog-outline"
              @click="settingsOpen = true"
            />
            <RDivider v-if="canDeletePlatform" />
            <RMenuItem
              v-if="canDeletePlatform"
              :label="t('platform.delete-platform', 'Delete platform')"
              icon="mdi-delete-outline"
              variant="danger"
              :disabled="deleting"
              @click="onDelete"
            />
          </RMenu>
        </template>
      </InfoPanel>
    </template>
  </GalleryShell>

  <!-- Settings & Firmware drawers — mounted at the view level so they
       survive scroll restoration without remounting. -->
  <PlatformSettingsDrawer
    v-if="currentPlatform"
    v-model="settingsOpen"
    :platform="currentPlatform"
  />
  <FirmwareDrawer
    v-if="currentPlatform"
    v-model="firmwareOpen"
    :platform="currentPlatform"
  />
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
/* Clamp the inner icon to the shrunken panel at xs — RPlatformIcon
   uses inline `width`/`height` from its `size` prop with no max
   constraints, so we override here. */
html[data-bp~="xs"] .r-v2-plat__panel-icon :deep(.r-platform-icon) {
  width: 100% !important;
  height: 100% !important;
}

/* ── Provider chip cluster ───────────────────────────────────────
   Compact pill that pairs the provider's logo with its remote ID.
   `--passive` (Flashpoint / HLTB / Libretro — no public lookup URL)
   drops the hover lift since clicking does nothing. */
.r-v2-plat__provider {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 2px 10px 2px 4px;
  border-radius: var(--r-radius-pill);
  background: var(--r-color-bg-elevated);
  border: 1px solid var(--r-color-border);
  color: var(--r-color-fg-secondary);
  font-size: 11px;
  font-weight: var(--r-font-weight-medium);
  font-variant-numeric: tabular-nums;
  text-decoration: none;
  transition:
    background var(--r-motion-fast) var(--r-motion-ease-out),
    border-color var(--r-motion-fast) var(--r-motion-ease-out),
    transform var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-v2-plat__provider:hover:not(.r-v2-plat__provider--passive) {
  background: var(--r-color-surface-hover);
  border-color: var(--r-color-border-strong);
  color: var(--r-color-fg);
  transform: translateY(-1px);
}
.r-v2-plat__provider--passive {
  cursor: default;
  pointer-events: none;
}
.r-v2-plat__provider-logo {
  width: 22px;
  height: 22px;
  border-radius: 4px;
  object-fit: contain;
  flex-shrink: 0;
}
.r-v2-plat__provider-label {
  white-space: nowrap;
}
</style>
