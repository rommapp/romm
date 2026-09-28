<script setup lang="ts">
// GameActions — the action row in the game-details header.
// Composes GameActionBtn atoms that are shared with the GameCard hover
// overlay so both surfaces stay visually and behaviourally in sync.
// The Play button uses the emphasized + withLabel variant to match the
// original white pill CTA; every other button is a circular glass icon
// button. The `more` action opens the shared GameActionsList.
//
// Right-side group (desktop only): completion + rating + difficulty
// pickers, separated from the main ribbon by a spacer. All three share
// MetricMenuBtn — the rating/difficulty trigger an RRating popup,
// completion triggers an RSlider popup. On phones these move into the
// status button's sheet (GameActionBtn `withMetrics`) to save a row.
// Writes are optimistic via useGameActions.setScore.
import { computed, onMounted, ref, toRef } from "vue";
import { useI18n } from "vue-i18n";
import { useRouter } from "vue-router";
import type { SimpleRom } from "@/stores/roms";
import { isInstallableRom } from "@/utils";
import GameActionBtn from "@/v2/components/GameActions/GameActionBtn.vue";
import MetricMenuBtn from "@/v2/components/GameActions/MetricMenuBtn.vue";
import { METRICS } from "@/v2/components/GameActions/metrics";
import DownloadOrInstallDialog from "@/v2/components/GameDetails/DownloadOrInstallDialog.vue";
import InstallButton from "@/v2/components/GameDetails/InstallButton.vue";
import { useBreakpoint } from "@/v2/composables/useBreakpoint";
import { useGameActions } from "@/v2/composables/useGameActions";
import { useGridNav } from "@/v2/composables/useGridNav";
import {
  startInstallAndNavigate,
  useInstallSession,
} from "@/v2/composables/useInstallSession";

defineOptions({ inheritAttrs: false });

const props = defineProps<{
  rom: SimpleRom;
}>();

const { t } = useI18n();
const router = useRouter();
const romRef = toRef(props, "rom");
const actions = useGameActions(() => romRef.value);

// Windows ROMs fork the Download button into a Download/Install choice (see
// DownloadOrInstallDialog) instead of getting a separate ribbon button.
// InstallButton only replaces Download while a session is actively running
// (progress + Abort) - Download must never disappear outright, so a
// finished/failed session still goes through the same picker dialog too;
// "Install" always installs, offering to clear an existing cache first
// rather than becoming a separate "Reinstall" (see
// confirmClearIfInstalled). Non-Windows ROMs never touch any of this -
// Download behaves exactly as it always has.
const isInstallablePlatform = computed(() => isInstallableRom(props.rom));
const install = useInstallSession(() => romRef.value);
onMounted(() => {
  if (!isInstallablePlatform.value) return;
  install.checkExisting();
});

const showInstallButton = computed(
  () => isInstallablePlatform.value && install.isActive.value,
);

const showDownloadOrInstall = ref(false);
// The picker always opens for a Windows ROM, regardless of workerAvailable -
// that check is a single, possibly-stale Redis lookup taken once per mount
// (see checkWorkerAvailable's own comment), and gating the click on it used
// to mean a false/stale read silently fell through to GameActionBtn's plain
// download fallback instead of ever offering Install, with no explanation.
// A genuinely unreachable worker now fails loudly instead - the backend is
// the actual source of truth, and startInstallAndNavigate already surfaces
// that failure in an error snackbar.
function onDownloadClick() {
  showDownloadOrInstall.value = true;
}
function chooseDownload() {
  showDownloadOrInstall.value = false;
  actions.download();
}
async function chooseInstall() {
  showDownloadOrInstall.value = false;
  // A no-op unless a cache already exists for this ROM - see the
  // composable's own docstring. Always proceeds to install either way.
  await install.confirmClearIfInstalled();
  startInstallAndNavigate(romRef.value, router);
}

// Shrink the ribbon on phones — the large (44px) buttons crowd the narrow
// column; the default (36px) size fits more per row and reads cleaner.
const { smAndDown } = useBreakpoint();
const btnSize = computed<"default" | "large">(() =>
  smAndDown.value ? "default" : "large",
);

// Single-row gamepad/keyboard nav across the action ribbon. The root is
// itself the row; cells are every action button (`.r-v2-game-btn`) plus
// the right-side metrics (`.r-v2-metric-btn`), skipping the layout
// spacer. On pad-modality autofocus, `focusFirst` lands on the first
// rendered button — Play if available (template renders it first when
// `canPlay`), otherwise Download.
const rootEl = ref<HTMLElement | null>(null);
useGridNav(rootEl, {
  getRows: () => (rootEl.value ? [rootEl.value] : []),
  getCells: (row) =>
    Array.from(
      row.querySelectorAll<HTMLElement>(".r-v2-game-btn, .r-v2-metric-btn"),
    ),
});
</script>

<template>
  <div ref="rootEl" class="game-actions">
    <GameActionBtn
      v-if="actions.canPlayLocally.value"
      :rom="rom"
      action="play"
      :size="btnSize"
      variant="emphasized"
      with-label
      link
    />
    <GameActionBtn
      v-if="actions.canPlayStream.value"
      :rom="rom"
      action="stream"
      :size="btnSize"
      variant="brand"
      with-label
      link
    />
    <!-- Only rendered while someone else is hosting an open session on this
         ROM, so it sits beside Stream rather than replacing it. -->
    <GameActionBtn
      v-if="actions.canJoinStream.value"
      :rom="rom"
      action="join"
      :size="btnSize"
      variant="emphasized"
      with-label
    />
    <div v-if="actions.canPlay.value" class="game-actions__break" />
    <GameActionBtn
      v-if="!showInstallButton && actions.canDownload.value"
      :rom="rom"
      action="download"
      :size="btnSize"
      variant="surface"
      :on-download-click="isInstallablePlatform ? onDownloadClick : undefined"
    />
    <InstallButton
      v-if="showInstallButton"
      :install="install"
      :rom="rom"
      :size="btnSize"
    />
    <GameActionBtn
      v-if="actions.canDownload.value"
      :rom="rom"
      action="copy-link"
      :size="btnSize"
      variant="surface"
    />
    <GameActionBtn
      v-if="actions.canShareQR.value"
      :rom="rom"
      action="qr"
      :size="btnSize"
      variant="surface"
    />
    <GameActionBtn
      v-if="actions.canOpenInFlashpoint.value"
      :rom="rom"
      action="flashpoint"
      :size="btnSize"
      variant="surface"
    />
    <GameActionBtn
      :rom="rom"
      action="favorite"
      :size="btnSize"
      variant="surface"
    />
    <GameActionBtn
      :rom="rom"
      action="collection"
      :size="btnSize"
      variant="surface"
    />
    <GameActionBtn
      :rom="rom"
      action="status"
      :size="btnSize"
      variant="surface"
      with-metrics
    />
    <GameActionBtn :rom="rom" action="more" :size="btnSize" variant="surface" />

    <!-- Desktop only: the metric pills sit in the ribbon. On phones they
         move into the status sheet (see the status button's `withMetrics`). -->
    <template v-if="rom.rom_user && !smAndDown">
      <div class="game-actions__spacer" />
      <MetricMenuBtn
        v-for="m in METRICS"
        :key="m.field"
        :kind="m.kind"
        :label="t(m.labelKey)"
        :icon-full="m.iconFull"
        :icon-empty="m.iconEmpty"
        :accent="m.accent"
        :step="m.step"
        :size="btnSize"
        :value="rom.rom_user?.[m.field] ?? 0"
        @update:value="(v) => actions.setScore(m.field, v)"
      />
    </template>

    <DownloadOrInstallDialog
      v-if="isInstallablePlatform"
      v-model="showDownloadOrInstall"
      @download="chooseDownload"
      @install="chooseInstall"
    />
  </div>
</template>

<style scoped>
.game-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 6px 0 4px;
  flex-wrap: wrap;
}
.game-actions__spacer {
  flex: 1;
  min-width: 16px;
}

/* Mobile: centre the ribbon. The metrics move into the status sheet on
   phones (they aren't rendered here), so no spacer/hairline is needed. */
html[data-bp~="sm-and-down"] .game-actions {
  justify-content: center;
  gap: 8px;
}
/* Full-width break after the Play CTA so it keeps its natural width but
   sits alone (centred) on its own row above the icon ribbon on phones.
   Collapsed on wider viewports so it has no effect there. */
.game-actions__break {
  display: none;
}
html[data-bp~="sm-and-down"] .game-actions__break {
  display: block;
  flex: 0 0 100%;
  height: 0;
}
</style>
