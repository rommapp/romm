<script setup lang="ts">
// Install — full-page mode for the server-side Windows installer
// (Proton/Wine + VNC), replacing the old InstallVncOverlay modal. Modeled on
// EmulatorJS.vue's structure and its data-bp responsive pattern, but unlike
// /ejs the sidebar and bottom bar stay visible in both the idle and
// installing states — only the center stage swaps between a start panel,
// a "starting up" spinner, and the VNC viewport.
//
// Reachable two ways: `startInstallAndNavigate` (GameActions/InstallButton)
// fires the start request while routing here, so a session is usually
// already in flight by the time this mounts; or a direct visit/bookmark/
// refresh, where nothing has been requested yet and the start panel's CTA
// drives the same detect-then-start flow itself.
import {
  RAlert,
  RBtn,
  RCard,
  RIcon,
  RProgressLinear,
  RSelect,
  RSpinner,
  RSwitch,
} from "@v2/lib";
import {
  computed,
  nextTick,
  onBeforeUnmount,
  onMounted,
  ref,
  watch,
} from "vue";
import { useI18n } from "vue-i18n";
import { useRoute, useRouter } from "vue-router";
import { ROUTES } from "@/plugins/router";
import installApi from "@/services/api/install";
import romApi from "@/services/api/rom";
import storeConfig from "@/stores/config";
import type { DetailedRom } from "@/stores/roms";
import { formatBytes } from "@/utils";
import GameCover from "@/v2/components/shared/GameCover.vue";
import { useInstallSession } from "@/v2/composables/useInstallSession";
import { usePageTitle } from "@/v2/composables/usePageTitle";

const { t } = useI18n();
const route = useRoute();
const router = useRouter();

const rom = ref<DetailedRom | null>(null);
const install = useInstallSession(() => rom.value);
const configStore = storeConfig();

const selectedInstallerPath = ref<string | null>(null);
const selectedProtonBuild = ref<string | null>(null);

// Other clients currently pulling this session's files live, and the
// server-wide bandwidth cap they all share - polled on the same cadence as
// useInstallSession's own session poll, but kept separate from it (that
// composable is also mounted by the ribbon InstallButton, which has no use
// for this data).
const STREAM_MANIFEST_POLL_INTERVAL_MS = 3000;
const viewerCount = ref(0);
const downloadSpeedLimitBytesPerSec = ref<number | null>(null);
let streamManifestTimer: ReturnType<typeof setTimeout> | null = null;
// Reschedule happens inside an async `finally`, so a plain "clear whatever
// timer id we're tracking" on unmount misses a call that's already in
// flight when the component goes away - it resolves anyway and schedules a
// fresh timer regardless. This flag is checked right before every
// reschedule so an in-flight call becomes a no-op once we're gone.
let streamManifestStopped = false;

async function pollStreamManifest() {
  if (!rom.value) return;
  try {
    const { data } = await installApi.getInstallStreamManifest(rom.value.id);
    viewerCount.value = data.viewer_count;
    downloadSpeedLimitBytesPerSec.value =
      data.download_speed_limit_bytes_per_sec ?? null;
  } catch {
    // No session yet (or it just got cleared) - leave the last-known
    // values in place rather than flashing back to zero/unlimited.
  } finally {
    if (!streamManifestStopped) {
      streamManifestTimer = setTimeout(
        pollStreamManifest,
        STREAM_MANIFEST_POLL_INTERVAL_MS,
      );
    }
  }
}

onMounted(async () => {
  const romResponse = await romApi.getRom({
    romId: parseInt(route.params.rom as string),
  });
  rom.value = romResponse.data;

  install.checkExisting();
  install.checkCandidates();
  install.fetchProtonBuilds();
  pollStreamManifest();
});

onBeforeUnmount(() => {
  streamManifestStopped = true;
  if (streamManifestTimer !== null) clearTimeout(streamManifestTimer);
  vncFocusStopped = true;
});

// The VNC iframe needs actual DOM focus for the browser to forward keydown
// events into it at all - without it, some installers (ones that need e.g.
// an arrow key to advance a page) silently get nothing. Focusing the
// `<iframe>` element itself isn't enough though: noVNC's own Keyboard.js
// grabs key events from its *canvas* specifically, inside its own document,
// which normally only happens via a real click into it. Since the normal
// deployment is same-origin (see vnc.py's _build_public_url), reach in and
// focus that canvas directly; noVNC connects asynchronously so the canvas
// may not exist yet the instant the iframe starts loading, hence the bounded
// retry. Falls back to just the outer iframe.focus() (still routes real
// keyboard input, just not guaranteed to arm noVNC's own grab) if
// contentDocument throws - the cross-origin deployment path
// (INSTALL_VNC_PUBLIC_BASE_URL unset).
const vncFrame = ref<HTMLIFrameElement | null>(null);
let vncFocusStopped = false;
function tryFocusVncCanvas(attemptsLeft = 15) {
  const frame = vncFrame.value;
  if (!frame || vncFocusStopped) return;
  frame.focus();
  try {
    const canvas = frame.contentDocument?.querySelector("canvas");
    if (canvas) {
      canvas.focus();
      return;
    }
  } catch {
    return;
  }
  if (attemptsLeft > 0) {
    setTimeout(() => tryFocusVncCanvas(attemptsLeft - 1), 300);
  }
}
watch(
  () => install.vncUrl.value,
  (url) => {
    if (url) nextTick(() => tryFocusVncCanvas());
  },
);

// Candidates that need unpacking first (archives, disc images) are offered
// as an "Installation Source"; the executable list then shows what's inside
// the selected one. Without any, only the executable picker exists.
const SOURCE_KINDS = new Set(["archive", "disc image"]);
const DIRECT_SOURCE = "__direct__";
const selectedSource = ref<string | null>(null);

const directCandidates = computed(() =>
  install.candidates.value.filter((c) => !SOURCE_KINDS.has(c.kind)),
);
const sourceCandidates = computed(() =>
  install.candidates.value.filter((c) => SOURCE_KINDS.has(c.kind)),
);
const usesSource = computed(
  () => selectedSource.value !== null && selectedSource.value !== DIRECT_SOURCE,
);

// Pre-fill the pickers the moment their data arrives, but never override a
// choice the user already made (e.g. candidates re-fetching after a session
// started). The default mirrors the server's own (top-ranked candidate).
watch(install.candidates, (list) => {
  if (selectedSource.value != null || list.length === 0) return;
  if (sourceCandidates.value.length === 0) {
    selectedSource.value = DIRECT_SOURCE;
  } else {
    selectedSource.value = SOURCE_KINDS.has(list[0].kind)
      ? list[0].path
      : DIRECT_SOURCE;
  }
});
watch(selectedSource, (source) => {
  selectedInstallerPath.value = null;
  if (source === null) return;
  if (source === DIRECT_SOURCE) {
    selectedInstallerPath.value = directCandidates.value[0]?.path ?? null;
  } else {
    install.fetchSourceCandidates(source);
  }
});
watch(install.sourceCandidates, (list) => {
  if (usesSource.value && selectedInstallerPath.value == null) {
    selectedInstallerPath.value = list[0]?.path ?? null;
  }
});
watch(install.protonBuilds, (list) => {
  if (selectedProtonBuild.value == null) {
    const defaultBuild = configStore.config.INSTALL_DEFAULT_PROTON_BUILD;
    const installedIds = new Set(
      list.filter((b) => b.installed).map((b) => b.id),
    );
    if (defaultBuild && installedIds.has(defaultBuild)) {
      selectedProtonBuild.value = defaultBuild;
    } else {
      selectedProtonBuild.value = list.find((b) => b.installed)?.id ?? null;
    }
  }
});

const sourceItems = computed(() => [
  ...(directCandidates.value.length > 0
    ? [{ title: t("rom.install-source-direct"), value: DIRECT_SOURCE }]
    : []),
  ...sourceCandidates.value.map((c) => ({ title: c.file_name, value: c.path })),
]);
const installerItems = computed(() =>
  usesSource.value
    ? install.sourceCandidates.value.map((c) => ({
        title: c.path,
        value: c.path,
      }))
    : directCandidates.value.map((c) => ({
        title: c.file_name,
        value: c.path,
      })),
);
const protonItems = computed(() =>
  install.protonBuilds.value.map((build) => ({
    title: build.label,
    value: build.id,
    disabled: !build.installed,
  })),
);

async function startInstall() {
  // A no-op unless a cache already exists for this ROM - see the
  // composable's own docstring. Always proceeds to install either way.
  await install.confirmClearIfInstalled();
  install.startWithPath(
    selectedInstallerPath.value ?? undefined,
    selectedProtonBuild.value ?? undefined,
    usesSource.value ? (selectedSource.value ?? undefined) : undefined,
  );
}

// The main button doubles as Abort while a run is in flight - cancelInstall
// already gates on its own confirm dialog, nothing extra to wire here.
function onMainButtonClick() {
  if (isBusy.value) {
    install.cancelInstall();
  } else {
    startInstall();
  }
}

// Same three-state pending copy as InstallButton's ribbon control — kept in
// sync there rather than shared, since each reads a slightly different
// prop shape off the same composable.
const pendingLabel = computed(() => {
  if (install.waitingForWorker.value) {
    return t("rom.install-waiting-for-worker");
  }
  if (install.state.value === "installing") {
    if (install.protonDownloadProgress.value !== null) {
      const pct = Math.round((install.protonDownloadProgress.value || 0) * 100);
      return t("rom.install-downloading-proton", {
        name: install.protonDownloadLabel.value ?? "unknown",
        pct,
      });
    }
    if (install.protonExtracting.value) {
      return t("rom.install-extracting-proton", {
        name: install.protonDownloadLabel.value ?? "unknown",
      });
    }
    if (install.phase.value && install.phaseDetail.value) {
      return t(
        install.phase.value === "mounting"
          ? "rom.install-mounting"
          : "rom.install-extracting",
        { name: install.phaseDetail.value },
      );
    }
    if (!install.vncUrl.value) {
      return t("rom.install-starting");
    }
  }
  switch (install.state.value) {
    case "streaming":
      return t("rom.install-copying");
    case "installing":
      return t("rom.install-starting");
    default:
      return t("rom.install-detecting");
  }
});

// One label, always - no separate "Reinstall" state. Pressing Install on an
// already-installed ROM offers to clear the old cache first (see
// confirmClearIfInstalled) rather than silently relabeling the button.
const startCtaLabel = computed(() => t("rom.install"));

function backToRom() {
  router.push({ name: ROUTES.ROM, params: { rom: rom.value?.id } });
}
function backToPlatform() {
  router.push({
    name: ROUTES.PLATFORM,
    params: { platform: rom.value?.platform_id },
  });
}

const title = computed(
  () => rom.value?.name || rom.value?.fs_name_no_ext || "",
);
usePageTitle(() =>
  title.value ? t("rom.install-page-title", { name: title.value }) : null,
);

const platformLabel = computed(
  () =>
    rom.value?.platform_custom_name || rom.value?.platform_display_name || "",
);

// RBtn's own `loading` prop replaces the label with a spinner rather than
// showing both - fine for a plain submit button, but this one needs to stay
// readable (and clickable, as Abort) for the whole (multi-minute) run, so
// the sidebar button builds its own spinner+label instead of using `loading`.
//
// Deliberately excludes awaitingInstallerPick: a session parked there is
// "manual mode" (server-side auto-pick found nothing confident - see
// start_install_session's own docstring) - the picker and "Install" CTA
// must stay usable, not get locked out behind a perpetual "Abort" button
// and a disabled combo.
const isBusy = computed(
  () =>
    (install.isActive.value && !install.awaitingInstallerPick.value) ||
    install.starting.value,
);

const downloadSpeedLimitLabel = computed(() =>
  downloadSpeedLimitBytesPerSec.value
    ? t("rom.install-speed-limit-value", {
        rate: formatBytes(downloadSpeedLimitBytesPerSec.value, 0),
      })
    : t("rom.install-speed-limit-unlimited"),
);
</script>

<template>
  <section v-if="rom" class="r-v2-install">
    <div class="r-v2-install__stage">
      <!-- VNC bridge is up: this is the installer itself. -->
      <div v-if="install.vncUrl.value" class="r-v2-install__vnc-wrap">
        <iframe
          ref="vncFrame"
          class="r-v2-install__vnc-frame"
          :src="install.vncUrl.value"
          :title="t('rom.install-view')"
          allow="clipboard-read; clipboard-write; fullscreen"
          allowfullscreen
        />
      </div>

      <!-- Session active but the sandbox hasn't reached the VNC bridge yet,
           or no session exists yet because the worker is still booting and
           the start request is being retried (see waitingForWorker). -->
      <div
        v-else-if="isBusy || install.waitingForWorker.value"
        class="r-v2-install__pending"
      >
        <RSpinner :size="40" />
        <p class="r-v2-install__pending-label">
          {{ pendingLabel }}
        </p>
        <RProgressLinear
          v-if="install.protonDownloadProgress.value !== null"
          class="r-v2-install__dl-progress"
          :model-value="install.protonDownloadProgress.value * 100"
          :height="6"
          :aria-label="pendingLabel"
        />
      </div>

      <!-- Idle (nothing requested yet) or terminal (done/failed/expired). -->
      <div v-else class="r-v2-install__start">
        <GameCover
          class="r-v2-install__cover"
          :rom="rom"
          :title="title"
          :identified="rom.is_identified ?? true"
          style-context="player"
        />
        <div class="r-v2-install__title-block">
          <h1 class="r-v2-install__title">
            {{ title }}
          </h1>
          <p class="r-v2-install__subtitle">
            {{ platformLabel }}
          </p>
        </div>
        <RBtn
          size="x-large"
          variant="flat"
          color="primary"
          prepend-icon="mdi-download-box-outline"
          :loading="install.starting.value"
          @click="startInstall"
        >
          {{ startCtaLabel }}
        </RBtn>
      </div>
    </div>

    <RCard class="r-v2-install__sidebar" variant="flat">
      <div class="r-v2-install__sidebar-head">
        <RIcon icon="mdi-cog-outline" size="14" />
        <span>{{ t("common.settings") }}</span>
      </div>
      <div class="r-v2-install__sidebar-body">
        <RAlert type="info" density="compact" variant="translucent">
          {{ t("rom.install-hint-default-path") }}
        </RAlert>

        <RBtn
          block
          variant="flat"
          :color="isBusy ? 'error' : 'primary'"
          :disabled="install.starting.value || install.cancelling.value"
          @click="onMainButtonClick"
        >
          <template #prepend>
            <RSpinner v-if="isBusy" :size="16" color="currentColor" />
            <RIcon v-else icon="mdi-download-box-outline" />
          </template>
          {{ isBusy ? t("rom.install-abort") : startCtaLabel }}
        </RBtn>

        <RSwitch
          :model-value="install.autoMode.value"
          :label="t('rom.install-auto-mode')"
          @update:model-value="install.setAutoMode"
        />
        <RAlert
          v-if="install.autoMode.value && install.autoStatus.value"
          :type="
            install.autoStatus.value === 'needs_manual' ? 'warning' : 'info'
          "
          density="compact"
          variant="translucent"
        >
          {{
            install.autoStatus.value === "needs_manual"
              ? t("rom.install-auto-mode-needs-manual")
              : t("rom.install-auto-mode-running", {
                  action: install.autoDetail.value ?? "…",
                })
          }}
        </RAlert>

        <RSelect
          v-if="sourceCandidates.length > 0"
          v-model="selectedSource"
          variant="outlined"
          density="comfortable"
          prefix-label="stacked"
          prepend-inner-icon="mdi-folder-zip-outline"
          hide-details
          :disabled="isBusy"
          :label="t('rom.install-source')"
          :items="sourceItems"
        />

        <RSelect
          v-if="
            installerItems.length > 0 || install.loadingSourceCandidates.value
          "
          v-model="selectedInstallerPath"
          :loading="install.loadingSourceCandidates.value"
          variant="outlined"
          density="comfortable"
          prefix-label="stacked"
          prepend-inner-icon="mdi-file-outline"
          hide-details
          :disabled="isBusy"
          :label="t('rom.install-select-file')"
          :items="installerItems"
        />

        <RSelect
          v-if="protonItems.length > 0"
          v-model="selectedProtonBuild"
          variant="outlined"
          density="comfortable"
          prefix-label="stacked"
          prepend-inner-icon="mdi-package-variant-closed"
          hide-details
          :disabled="isBusy"
          :label="t('rom.install-proton-version')"
          :items="protonItems"
        />

        <div v-if="install.session.value" class="r-v2-install__cache-actions">
          <RBtn
            block
            variant="outlined"
            size="small"
            prepend-icon="mdi-folder-zip-outline"
            :disabled="!install.hasCache.value"
            @click="installApi.downloadInstallCache(rom.id)"
          >
            {{ t("rom.install-download-cache") }}
          </RBtn>
          <RBtn
            block
            variant="outlined"
            size="small"
            color="error"
            prepend-icon="mdi-database-remove"
            :loading="install.clearingCache.value"
            :disabled="!install.hasCache.value"
            :title="
              install.hasCache.value
                ? undefined
                : t('rom.install-clear-cache-disabled-hint')
            "
            @click="install.clearCache"
          >
            {{ t("rom.install-clear-cache") }}
          </RBtn>
        </div>
      </div>
      <div class="r-v2-install__sidebar-foot">
        <div class="r-v2-install__meta">
          <span class="r-v2-install__meta-row">
            <RIcon icon="mdi-account-multiple-outline" size="14" />
            {{ t("rom.install-viewers-count", { n: viewerCount }) }}
          </span>
          <span class="r-v2-install__meta-row">
            <RIcon icon="mdi-speedometer" size="14" />
            {{ downloadSpeedLimitLabel }}
          </span>
        </div>
      </div>
    </RCard>

    <div class="r-v2-install__bottombar">
      <RBtn
        variant="text"
        size="small"
        prepend-icon="mdi-arrow-left"
        @click="backToRom"
      >
        {{ t("play.back-to-game-details") }}
      </RBtn>
      <RBtn
        variant="text"
        size="small"
        prepend-icon="mdi-view-grid-outline"
        @click="backToPlatform"
      >
        {{ t("play.back-to-gallery") }}
      </RBtn>
    </div>
  </section>

  <section v-else class="r-v2-install__loading">
    <RSpinner :size="40" :label="t('common.loading')" />
  </section>
</template>

<style scoped>
.r-v2-install__cache-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.r-v2-install {
  min-height: calc(100vh - var(--r-nav-h));
  padding: 24px var(--r-row-pad) 24px;
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(260px, 300px);
  grid-template-rows: minmax(420px, 1fr) auto;
  grid-template-areas:
    "stage sidebar"
    "bottombar bottombar";
  gap: 16px;
  max-width: 1400px;
  margin: 0 auto;
}

/* ── Center stage ────────────────────────────────────────── */
.r-v2-install__stage {
  grid-area: stage;
  position: relative;
  display: flex;
  border-radius: var(--r-radius-lg);
  overflow: hidden;
  background: var(--r-color-canvas-bg);
  border: 1px solid var(--r-color-border);
}
.r-v2-install__vnc-wrap {
  position: relative;
  width: 100%;
  height: 100%;
}
.r-v2-install__vnc-frame {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  border: 0;
  background: var(--r-color-canvas-bg-deep);
}

.r-v2-install__start,
.r-v2-install__pending {
  margin: auto;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 14px;
  padding: 32px;
  text-align: center;
  color: var(--r-color-fg-secondary);
}
.r-v2-install__pending-label {
  color: var(--r-color-overlay-fg);
}
.r-v2-install__dl-progress {
  width: 220px;
}
.r-v2-install__cover {
  width: 100%;
  max-width: 200px;
  --r-cover-radius: var(--r-radius-md);
  box-shadow:
    0 18px 36px color-mix(in srgb, black 55%, transparent),
    0 0 0 1px var(--r-color-border);
}
.r-v2-install__title-block {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.r-v2-install__title {
  margin: 0;
  font-size: var(--r-font-size-lg);
  font-weight: var(--r-font-weight-bold);
  color: var(--r-color-fg);
}
.r-v2-install__subtitle {
  margin: 0;
  font-size: var(--r-font-size-sm);
  color: var(--r-color-fg-muted);
}

/* ── Right sidebar ───────────────────────────────────────── */
.r-v2-install__sidebar {
  grid-area: sidebar;
  backdrop-filter: blur(18px);
  display: flex !important;
  flex-direction: column;
  overflow: hidden;
}
.r-v2-install__sidebar-head {
  padding: 14px 14px 0;
  display: flex;
  align-items: center;
  gap: 8px;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  font-size: 11px;
  font-weight: var(--r-font-weight-semibold);
  color: var(--r-color-fg-secondary);
}
.r-v2-install__sidebar-body {
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  flex: 1;
}
.r-v2-install__sidebar-foot {
  border-top: 1px solid var(--r-color-border);
  padding: 6px 10px 10px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.r-v2-install__meta {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 4px 4px 0;
}
.r-v2-install__meta-row {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: var(--r-color-fg-muted);
}

/* ── Bottom bar ──────────────────────────────────────────── */
.r-v2-install__bottombar {
  grid-area: bottombar;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  border-top: 1px solid var(--r-color-border);
  padding-top: 10px;
}

.r-v2-install__loading {
  min-height: calc(100vh - var(--r-nav-h));
  display: grid;
  place-items: center;
}

/* ── Responsive ──────────────────────────────────────────── */
html[data-bp~="sm-and-down"] .r-v2-install {
  grid-template-columns: 1fr;
  grid-template-rows: auto auto auto;
  grid-template-areas:
    "stage"
    "sidebar"
    "bottombar";
}
html[data-bp~="sm-and-down"] .r-v2-install__stage {
  min-height: 280px;
}
</style>
