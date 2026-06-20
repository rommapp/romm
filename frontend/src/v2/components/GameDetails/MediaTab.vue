<script setup lang="ts">
// Combined Manual + Soundtrack + Screenshots tab for GameDetails.
//
// Behaviour:
//   * Subtabs always rendered; empty states drive the upload CTAs
//   * Each panel doubles as a drag-and-drop target (same affordance as the
//     Upload / Patcher views): drop files anywhere over the active panel to
//     upload them
//   * Hidden file inputs back the explicit upload buttons — manual upload
//     routes through `showManualUploadTargetDialog` (dialog mounted in
//     AppLayout); soundtrack upload goes through `romApi.uploadSoundtracks`
//   * Re-download primary manual + delete manual both handled here
//   * The screenshots subtab is its own component (ScreenshotsSubtab):
//     ROM / Mine / Community sections with per-user public/private
//
// The PDF viewer + soundtrack player are reused from v1 for now.
import {
  RBtn,
  RCollapsible,
  RDropzone,
  REmptyState,
  RIcon,
  RSelect,
} from "@v2/lib";
import axios from "axios";
import type { Emitter } from "mitt";
import { computed, defineAsyncComponent, inject, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute, useRouter } from "vue-router";
import romApi from "@/services/api/rom";
import storeRoms, { type DetailedRom } from "@/stores/roms";
import storeUpload from "@/stores/upload";
import type { Events } from "@/types/emitter";
import { FRONTEND_RESOURCES_PATH } from "@/utils";
import { useConfirm } from "@/v2/composables/useConfirm";
import { useSnackbar } from "@/v2/composables/useSnackbar";

const PdfViewer = defineAsyncComponent(
  () => import("@/v2/components/GameDetails/PdfViewer.vue"),
);
const SoundtrackPanel = defineAsyncComponent(
  () => import("@/v2/components/GameDetails/SoundtrackPanel.vue"),
);
const ScreenshotsSubtab = defineAsyncComponent(
  () => import("@/v2/components/GameDetails/ScreenshotsSubtab.vue"),
);

function errorMessage(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const detail = err.response?.data?.detail;
    if (typeof detail === "string" && detail) return detail;
    return err.message;
  }
  return err instanceof Error ? err.message : String(err);
}

const props = defineProps<{ rom: DetailedRom }>();
const emitter = inject<Emitter<Events>>("emitter");
const snackbar = useSnackbar();
const confirm = useConfirm();
const romsStore = storeRoms();
const uploadStore = storeUpload();
const { t } = useI18n();

// ---------- Subtab state ----------
// Mirrored to `?subtab=` so the SoundtrackMiniPlayer can detect when the full
// player is visible here and hide itself to avoid duplication.
const validSubtabs = ["manual", "soundtrack", "screenshots"] as const;
type Subtab = (typeof validSubtabs)[number];

const route = useRoute();
const router = useRouter();

const subTab = ref<Subtab>(
  validSubtabs.includes(route.query.subtab as Subtab)
    ? (route.query.subtab as Subtab)
    : "manual",
);

watch(subTab, (value) => {
  if (route.query.subtab !== value) {
    router.replace({
      path: route.path,
      query: { ...route.query, subtab: value },
    });
  }
});

watch(
  () => route.query.subtab,
  (value) => {
    if (typeof value === "string" && validSubtabs.includes(value as Subtab)) {
      subTab.value = value as Subtab;
    }
  },
);

// When the user navigates away from the Media tab, drop the subtab query
// param so stale state doesn't leak onto other tabs.
watch(
  () => route.query.tab,
  (value) => {
    if (value !== "media" && route.query.subtab) {
      const rest = { ...route.query };
      delete rest.subtab;
      router.replace({ path: route.path, query: rest });
    }
  },
);

// ---------- Manual entries ----------
type ManualEntry = {
  id: string;
  label: string;
  url: string;
  isPrimary: boolean;
};

const manualEntries = computed<ManualEntry[]>(() => {
  const entries: ManualEntry[] = [];
  const cacheBust = encodeURIComponent(props.rom.updated_at);
  if (props.rom.has_manual && props.rom.path_manual) {
    entries.push({
      id: "primary",
      label: t("rom.scraped-manual"),
      url: `${FRONTEND_RESOURCES_PATH}/${props.rom.path_manual}?v=${cacheBust}`,
      isPrimary: true,
    });
  }
  for (const file of props.rom.files ?? []) {
    if (file.category === "manual") {
      entries.push({
        id: `file-${file.id}`,
        label: file.file_name.replace(/\.[^.]+$/, ""),
        url: `/api/roms/${file.id}/files/content/${encodeURIComponent(
          file.file_name,
        )}?v=${cacheBust}`,
        isPrimary: false,
      });
    }
  }
  return entries;
});

const selectedManualId = ref<string>("");
let previousManualIds = new Set<string>();

watch(
  manualEntries,
  (entries) => {
    const currentIds = new Set(entries.map((e) => e.id));
    if (entries.length === 0) {
      selectedManualId.value = "";
    } else {
      // If a new entry appears after a prior snapshot, select it so the user
      // lands on the manual they just uploaded.
      const added = entries.filter((e) => !previousManualIds.has(e.id));
      if (added.length > 0 && previousManualIds.size > 0) {
        selectedManualId.value = added[added.length - 1].id;
      } else if (!entries.some((e) => e.id === selectedManualId.value)) {
        selectedManualId.value = entries[0].id;
      }
    }
    previousManualIds = currentIds;
  },
  { immediate: true },
);

const selectedManual = computed(() =>
  manualEntries.value.find((e) => e.id === selectedManualId.value),
);
const manualItems = computed(() =>
  manualEntries.value.map((e) => ({ title: e.label, value: e.id })),
);

// ---------- Soundtrack gating ----------
// Soundtracks live alongside the ROM folder, so single-file ROMs can't have
// one. Mirror the v1 gate.
const soundtrackSupported = computed(() => !props.rom.has_simple_single_file);

// ---------- Subtab nav ----------
// We render the subtab list manually (not via RTabNav) so we can inline
// each subtab's contextual controls right under the active item — the
// list reads as "tab + its expanded panel", not "tabs above + a separate
// actions block". RTabNav stays a navigation-only primitive.
type SubtabDef = { id: Subtab; label: string; icon: string };
const subtabDefs = computed<SubtabDef[]>(() => [
  {
    id: "manual",
    label: t("rom.manual"),
    icon: "mdi-book-open-page-variant-outline",
  },
  {
    id: "soundtrack",
    label: t("rom.soundtrack"),
    icon: "mdi-music-note-outline",
  },
  {
    id: "screenshots",
    label: t("rom.screenshots"),
    icon: "mdi-image-multiple-outline",
  },
]);

// Whether the active subtab has any inline actions worth rendering.
// Drives the empty-panel skip so we don't paint a stray padding block.
function hasSubtabActions(id: Subtab): boolean {
  if (id === "manual") return manualEntries.value.length > 0;
  if (id === "soundtrack")
    return soundtrackSupported.value && Boolean(props.rom.has_soundtrack);
  // The screenshots subtab owns its own controls (ScreenshotsSubtab).
  return false;
}

// ---------- Upload / refresh plumbing ----------
// The manual / soundtrack panels each use an RDropzone (CTA when empty,
// overlay over the viewer / player when filled). The sidebar's explicit
// "upload" button opens the filled dropzone's picker via these refs.
const manualDz = ref<InstanceType<typeof RDropzone> | null>(null);
const soundtrackDz = ref<InstanceType<typeof RDropzone> | null>(null);
const redownloadingManual = ref(false);

async function refreshRom() {
  try {
    const { data } = await romApi.getRom({ romId: props.rom.id });
    romsStore.currentRom = data;
    romsStore.update(data);
  } catch (error) {
    console.error(error);
  }
}

// ---------- File handlers (shared by file input + drag-and-drop) ----------
// Manual upload routes through the target-selection dialog (mounted in
// AppLayout): the user picks which platform/folder the manual belongs to,
// so we hand off rather than uploading inline.
function handleManualFiles(files: File[]) {
  if (files.length === 0) return;
  emitter?.emit("showManualUploadTargetDialog", { rom: props.rom, files });
}

async function handleSoundtrackFiles(files: File[]) {
  if (files.length === 0 || !soundtrackSupported.value) return;

  const responses = await romApi.uploadSoundtracks({
    romId: props.rom.id,
    filesToUpload: files,
  });

  const successful = responses.filter((r) => r.status === "fulfilled").length;
  const failed = responses.length - successful;

  if (failed === 0) uploadStore.reset();

  if (successful > 0) {
    snackbar.success(
      failed
        ? t("rom.tracks-uploaded-with-failed", successful, {
            named: { n: successful, failed },
          })
        : t("rom.tracks-uploaded-n", successful, {
            named: { n: successful },
          }),
      { icon: "mdi-check-bold", timeout: 3000 },
    );
    await refreshRom();
  } else {
    snackbar.warning(t("rom.no-tracks-uploaded"), {
      icon: "mdi-close-circle",
      timeout: 5000,
    });
  }
}

async function redownloadManual() {
  if (redownloadingManual.value) return;
  redownloadingManual.value = true;
  try {
    await romApi.redownloadManual({ romId: props.rom.id });
    await refreshRom();
    snackbar.success(t("rom.manual-redownloaded"), {
      icon: "mdi-check-bold",
    });
  } catch (error: unknown) {
    snackbar.error(
      t("rom.manual-redownload-failed", { error: errorMessage(error) }),
      {
        icon: "mdi-close-circle",
      },
    );
  } finally {
    redownloadingManual.value = false;
  }
}

function requestDeleteManual() {
  const entry = selectedManual.value;
  if (!entry) return;
  emitter?.emit("showDeleteManualDialog", {
    rom: props.rom,
    isPrimary: entry.isPrimary,
    fileId: entry.isPrimary
      ? undefined
      : Number(entry.id.replace(/^file-/, "")),
  });
}

async function deleteSoundtrack(fileId: number) {
  // Mirrors the saves/states pattern in SaveDataTab — every destructive
  // per-row action confirms before hitting the API.
  const track = (props.rom.files ?? []).find((f) => f.id === fileId);
  const name = track?.file_name ?? "";
  const ok = await confirm({
    title: t("rom.delete-track-title"),
    body: name
      ? t("rom.delete-track-body-named", { name })
      : t("rom.delete-track-body"),
    confirmText: t("rom.soundtrack-delete-track"),
    tone: "danger",
  });
  if (!ok) return;
  try {
    await romApi.removeSoundtrack({ romId: props.rom.id, fileId });
    await refreshRom();
    snackbar.success(t("rom.soundtrack-removed"), { icon: "mdi-check-bold" });
  } catch (error: unknown) {
    snackbar.error(
      t("rom.soundtrack-remove-failed", { error: errorMessage(error) }),
      {
        icon: "mdi-close-circle",
      },
    );
  }
}
</script>

<template>
  <div class="r-v2-media">
    <aside class="r-v2-media__sidebar">
      <ul
        class="r-v2-media__subtabs"
        role="tablist"
        aria-orientation="vertical"
      >
        <li
          v-for="tab in subtabDefs"
          :key="tab.id"
          class="r-v2-media__subtab"
          :class="{ 'r-v2-media__subtab--active': subTab === tab.id }"
        >
          <button
            type="button"
            role="tab"
            class="r-v2-media__subtab-btn"
            :class="{
              'r-v2-media__subtab-btn--active': subTab === tab.id,
              'r-v2-media__subtab-btn--joined':
                subTab === tab.id && hasSubtabActions(tab.id),
            }"
            :aria-selected="subTab === tab.id"
            @click="subTab = tab.id"
          >
            <RIcon :icon="tab.icon" size="16" />
            <span class="r-v2-media__subtab-label">{{ tab.label }}</span>
          </button>

          <!-- Inline controls panel — RCollapsible drives the open/close
               animation; `attached` removes its top radius/border so it
               sits flush with the active subtab button above. -->
          <RCollapsible
            :model-value="subTab === tab.id && hasSubtabActions(tab.id)"
            attached
            class="r-v2-media__subtab-panel"
          >
            <div class="r-v2-media__subtab-panel-inner">
              <template v-if="tab.id === 'manual' && manualEntries.length > 0">
                <RSelect
                  v-if="manualEntries.length > 1"
                  v-model="selectedManualId"
                  :items="manualItems"
                  density="compact"
                  variant="outlined"
                  hide-details
                />
                <RBtn
                  variant="outlined"
                  prepend-icon="mdi-cloud-upload-outline"
                  block
                  @click="manualDz?.open()"
                >
                  {{ t("common.upload") }}
                </RBtn>
                <RBtn
                  v-if="rom.url_manual"
                  variant="outlined"
                  prepend-icon="mdi-cloud-download-outline"
                  block
                  :loading="redownloadingManual"
                  :disabled="redownloadingManual"
                  @click="redownloadManual"
                >
                  {{ t("rom.redownload") }}
                </RBtn>
                <RBtn
                  v-if="selectedManual"
                  variant="outlined"
                  color="romm-red"
                  prepend-icon="mdi-delete"
                  block
                  @click="requestDeleteManual"
                >
                  {{ t("common.delete") }}
                </RBtn>
              </template>

              <template
                v-else-if="
                  tab.id === 'soundtrack' &&
                  soundtrackSupported &&
                  rom.has_soundtrack
                "
              >
                <RBtn
                  variant="outlined"
                  prepend-icon="mdi-cloud-upload-outline"
                  block
                  @click="soundtrackDz?.open()"
                >
                  {{ t("common.upload") }}
                </RBtn>
              </template>
            </div>
          </RCollapsible>
        </li>
      </ul>
    </aside>

    <div class="r-v2-media__content">
      <!-- All three subtab sections stay mounted (v-show, not v-if).
           PdfViewer, SoundtrackPanel and ScreenshotsTab are heavy
           defineAsyncComponent loads — un/remounting them on every
           subtab switch causes a visible main-thread freeze (the PDF
           parser is the worst offender). With v-show the cost is paid
           once on Media tab entry and switching is a CSS toggle. -->
      <!-- Manual subtab -->
      <section v-show="subTab === 'manual'" class="r-v2-media__panel">
        <RDropzone
          v-if="manualEntries.length === 0"
          :title="t('rom.manual-empty')"
          :hint="t('common.dropzone-hint')"
          :active-title="t('common.dropzone-drag-over')"
          :input-label="t('rom.upload-manual')"
          accept="application/pdf"
          multiple
          @files="handleManualFiles"
        >
          <template v-if="rom.url_manual" #actions>
            <RBtn
              variant="outlined"
              prepend-icon="mdi-cloud-download-outline"
              :loading="redownloadingManual"
              :disabled="redownloadingManual"
              @click.stop="redownloadManual"
            >
              {{ t("rom.redownload") }}
            </RBtn>
          </template>
        </RDropzone>

        <RDropzone
          v-else
          ref="manualDz"
          overlay
          class="r-v2-media__fill"
          :release-label="t('common.dropzone-drag-over')"
          :input-label="t('rom.upload-manual')"
          accept="application/pdf"
          multiple
          @files="handleManualFiles"
        >
          <div class="r-v2-media__viewer">
            <PdfViewer
              v-if="selectedManual"
              :key="`${selectedManual.id}-${rom.updated_at}`"
              :pdf-url="selectedManual.url"
            />
          </div>
        </RDropzone>
      </section>

      <!-- Soundtrack subtab -->
      <section v-show="subTab === 'soundtrack'" class="r-v2-media__panel">
        <REmptyState
          v-if="!soundtrackSupported"
          icon="mdi-music-off"
          :title="t('rom.soundtrack-no-folder')"
          :hint="t('rom.soundtrack-folder-hint')"
        />

        <RDropzone
          v-else-if="!rom.has_soundtrack"
          :title="t('rom.soundtrack-empty')"
          :hint="t('common.dropzone-hint')"
          :active-title="t('common.dropzone-drag-over')"
          :input-label="t('rom.upload-soundtrack')"
          accept="audio/*,.flac,.opus"
          multiple
          @files="handleSoundtrackFiles"
        />

        <RDropzone
          v-else
          ref="soundtrackDz"
          overlay
          :release-label="t('common.dropzone-drag-over')"
          :input-label="t('rom.upload-soundtrack')"
          accept="audio/*,.flac,.opus"
          multiple
          @files="handleSoundtrackFiles"
        >
          <SoundtrackPanel
            :rom="rom"
            class="r-v2-media__soundtrack"
            @upload-tracks="soundtrackDz?.open()"
            @delete-track="deleteSoundtrack"
          />
        </RDropzone>
      </section>

      <!-- Screenshots subtab — its own component (ROM / Mine / Community
           sections, per-user public/private). -->
      <section v-show="subTab === 'screenshots'" class="r-v2-media__panel">
        <ScreenshotsSubtab :rom="rom" />
      </section>
    </div>
  </div>
</template>

<style scoped>
.r-v2-media {
  display: flex;
  align-items: stretch;
  gap: 24px;
  /* Fills the parent tab panel exactly so the PDF viewer (inside the
     manual section) can size to 100% without forcing the outer panel
     to scroll — the PDF has its own internal scroll. */
  height: 100%;
  min-height: 0;
}

.r-v2-media__sidebar {
  width: 220px;
  flex-shrink: 0;
}

/* Subtab list — inline-expansion pattern: each tab can host a panel of
   contextual actions right under its button. Visual mirrors RTabNav's
   `pill` + `vertical` + `sm` size so the navigation reads identically
   to the rest of v2. */
.r-v2-media__subtabs {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.r-v2-media__subtab {
  display: flex;
  flex-direction: column;
}
.r-v2-media__subtab-btn {
  width: 100%;
  appearance: none;
  background: transparent;
  border: none;
  cursor: pointer;
  text-align: left;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: var(--r-radius-md);
  color: var(--r-color-fg-muted);
  font-family: inherit;
  font-size: 12px;
  font-weight: var(--r-font-weight-medium);
  transition:
    background var(--r-motion-fast) var(--r-motion-ease-out),
    color var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-v2-media__subtab-btn:hover {
  background: var(--r-color-surface-hover);
  color: var(--r-color-fg);
}
.r-v2-media__subtab-btn--active {
  background: color-mix(in srgb, var(--r-color-brand-primary) 18%, transparent);
  color: var(--r-color-brand-primary);
}
/* When the active subtab has an attached panel below, drop its bottom
   radius so the button visually merges with the RCollapsible surface. */
.r-v2-media__subtab-btn--joined {
  border-bottom-left-radius: 0;
  border-bottom-right-radius: 0;
}
.r-v2-media__subtab-label {
  flex: 1;
}

/* Inline panel — RCollapsible (attached, headless) provides the
   surface (bg-elevated + border + bottom radius) and the open/close
   animation. We only add a small bottom margin so the next subtab
   doesn't crowd the panel. */
.r-v2-media__subtab-panel {
  margin-bottom: var(--r-space-1);
}
/* Headless mode: consumer drives the inner padding so the controls
   breathe inside the panel surface. */
.r-v2-media__subtab-panel-inner {
  display: flex;
  flex-direction: column;
  gap: var(--r-space-2);
  padding: var(--r-space-3);
}

.r-v2-media__content {
  flex: 1;
  min-width: 0;
  /* Flex column so the active subtab section (the only visible one
     via v-show) can use `flex: 1` to fill the row's height. */
  display: flex;
  flex-direction: column;
  min-height: 0;
}

/* Panels — each subtab section fills the content height so its
   children (PDF viewer / soundtrack / screenshots) can stretch
   to 100% without forcing an outer scrollbar. */
.r-v2-media__panel {
  display: flex;
  flex-direction: column;
  gap: var(--r-space-3);
  flex: 1;
  min-height: 0;
}

/* Overlay-mode RDropzone wrapping the PDF viewer must fill the panel
   height so the inner viewer can stretch to 100%. */
.r-v2-media__fill {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

html[data-bp~="xs"] .r-v2-media {
  flex-direction: column;
  gap: 14px;
}
html[data-bp~="xs"] .r-v2-media__sidebar {
  width: auto;
}

/* Manual viewer — fills the available panel height so the inner PDF
   uses 100% and only its own scroll triggers (no outer panel scroll). */
.r-v2-media__viewer {
  flex: 1;
  min-height: 0;
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-md);
  overflow: hidden;
  background: var(--r-color-bg-elevated);
}

/* Soundtrack — the v1 player has its own internal styling; wrap in an
   elevated container so it blends with v2 tokens. */
.r-v2-media__soundtrack {
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-md);
  background: var(--r-color-bg-elevated);
}
</style>
