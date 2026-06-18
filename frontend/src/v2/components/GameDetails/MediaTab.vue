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
//     AppLayout); soundtrack + screenshot uploads go straight through
//     `romApi.uploadSoundtracks` / `romApi.uploadScreenshots`
//   * Re-download primary manual + delete manual both handled here
//   * Screenshots are user-uploaded images stored alongside the ROM (the
//     `screenshots/` folder); scraped screenshots live in the Overview tab
//
// The PDF viewer + soundtrack player are reused from v1 for now.
import { RBtn, RCollapsible, REmptyState, RIcon, RSelect } from "@v2/lib";
import { useDropZone } from "@vueuse/core";
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
const ScreenshotsTab = defineAsyncComponent(
  () => import("@/v2/components/GameDetails/ScreenshotsTab.vue"),
);

// File extensions we treat as previewable images in the user
// screenshots gallery. Mirrors the canonical "Web Images" set —
// includes WebP and AVIF since modern browsers all decode them.
const IMAGE_EXTENSIONS = new Set([
  "png",
  "jpg",
  "jpeg",
  "webp",
  "gif",
  "bmp",
  "avif",
]);

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

// ---------- User screenshots (filesystem-backed) ----------
// User-uploaded images live in the ROM's `screenshots/` (or `screenshot/`)
// subfolder. Uploads go through `romApi.uploadScreenshots`; manually-dropped
// files (added straight to the filesystem) are surfaced too. URLs route
// through the same `/api/roms/{file_id}/files/content/{name}` endpoint used
// by manual / soundtrack downloads.
const userScreenshots = computed<{ id: number; url: string }[]>(() => {
  const cacheBust = encodeURIComponent(props.rom.updated_at);
  const out: { id: number; url: string }[] = [];
  for (const file of props.rom.files ?? []) {
    const rel = file.full_path
      .replace(props.rom.full_path, "")
      .replace(/^\//, "");
    const firstSegment = rel.split("/")[0]?.toLowerCase();
    if (firstSegment !== "screenshots" && firstSegment !== "screenshot") {
      continue;
    }
    const ext = file.file_name.split(".").pop()?.toLowerCase() ?? "";
    if (!IMAGE_EXTENSIONS.has(ext)) continue;
    out.push({
      id: file.id,
      url: `/api/roms/${file.id}/files/content/${encodeURIComponent(
        file.file_name,
      )}?v=${cacheBust}`,
    });
  }
  return out;
});

// Screenshots, like soundtracks, live alongside the ROM folder — single-file
// ROMs can't host them.
const screenshotsSupported = computed(() => !props.rom.has_simple_single_file);

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
  if (id === "screenshots")
    return screenshotsSupported.value && userScreenshots.value.length > 0;
  return false;
}

// ---------- Upload / refresh plumbing ----------
const manualUploadInput = ref<HTMLInputElement | null>(null);
const soundtrackUploadInput = ref<HTMLInputElement | null>(null);
const screenshotUploadInput = ref<HTMLInputElement | null>(null);
const redownloadingManual = ref(false);

function triggerManualUpload() {
  manualUploadInput.value?.click();
}

function triggerSoundtrackUpload() {
  soundtrackUploadInput.value?.click();
}

function triggerScreenshotUpload() {
  screenshotUploadInput.value?.click();
}

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
        ? t("rom.tracks-uploaded-with-failed", { n: successful, failed })
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

async function handleScreenshotFiles(files: File[]) {
  if (files.length === 0 || !screenshotsSupported.value) return;

  const responses = await romApi.uploadScreenshots({
    romId: props.rom.id,
    filesToUpload: files,
  });

  const successful = responses.filter((r) => r.status === "fulfilled").length;
  const failed = responses.length - successful;

  if (failed === 0) uploadStore.reset();

  if (successful > 0) {
    snackbar.success(
      failed
        ? t("rom.screenshots-uploaded-with-failed", { n: successful, failed })
        : t("rom.screenshots-uploaded-n", successful, {
            named: { n: successful },
          }),
      { icon: "mdi-check-bold", timeout: 3000 },
    );
    await refreshRom();
  } else {
    snackbar.warning(t("rom.no-screenshots-uploaded"), {
      icon: "mdi-close-circle",
      timeout: 5000,
    });
  }
}

function onManualUpload(event: Event) {
  const input = event.target as HTMLInputElement;
  const files = input.files ? Array.from(input.files) : [];
  input.value = "";
  handleManualFiles(files);
}

async function onSoundtrackUpload(event: Event) {
  const input = event.target as HTMLInputElement;
  const files = input.files ? Array.from(input.files) : [];
  input.value = "";
  await handleSoundtrackFiles(files);
}

async function onScreenshotUpload(event: Event) {
  const input = event.target as HTMLInputElement;
  const files = input.files ? Array.from(input.files) : [];
  input.value = "";
  await handleScreenshotFiles(files);
}

// ---------- Drag-and-drop ----------
// Each panel doubles as a drop target (same affordance as the Upload /
// Patcher views). Soundtrack / screenshot drops are gated to folder-based
// ROMs — their handlers no-op otherwise and the overlay stays hidden, so we
// never invite a drop that would silently fail.
const manualPanelRef = ref<HTMLElement | null>(null);
const soundtrackPanelRef = ref<HTMLElement | null>(null);
const screenshotPanelRef = ref<HTMLElement | null>(null);

const { isOverDropZone: isOverManualDrop } = useDropZone(manualPanelRef, {
  onDrop(files) {
    if (files) handleManualFiles(files);
  },
  multiple: true,
  preventDefaultForUnhandled: true,
});
const { isOverDropZone: isOverSoundtrackDrop } = useDropZone(
  soundtrackPanelRef,
  {
    onDrop(files) {
      if (files) void handleSoundtrackFiles(files);
    },
    multiple: true,
    preventDefaultForUnhandled: true,
  },
);
const { isOverDropZone: isOverScreenshotDrop } = useDropZone(
  screenshotPanelRef,
  {
    onDrop(files) {
      if (files) void handleScreenshotFiles(files);
    },
    multiple: true,
    preventDefaultForUnhandled: true,
  },
);

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

async function deleteScreenshot(fileId: number) {
  // Mirrors the soundtrack delete flow — every destructive per-item action
  // confirms before hitting the API.
  const shot = (props.rom.files ?? []).find((f) => f.id === fileId);
  const name = shot?.file_name ?? "";
  const ok = await confirm({
    title: t("rom.delete-screenshot-title"),
    body: name
      ? t("rom.delete-screenshot-body-named", { name })
      : t("rom.delete-screenshot-body"),
    confirmText: t("common.delete"),
    tone: "danger",
  });
  if (!ok) return;
  try {
    await romApi.removeScreenshot({ romId: props.rom.id, fileId });
    await refreshRom();
    snackbar.success(t("rom.screenshot-removed"), { icon: "mdi-check-bold" });
  } catch (error: unknown) {
    snackbar.error(
      t("rom.screenshot-remove-failed", { error: errorMessage(error) }),
      {
        icon: "mdi-close-circle",
      },
    );
  }
}
</script>

<template>
  <!-- Hidden file inputs drive the upload buttons -->
  <input
    ref="manualUploadInput"
    type="file"
    accept="application/pdf"
    multiple
    class="r-v2-media__file-input"
    :aria-label="t('rom.upload-manual')"
    @change="onManualUpload"
  />
  <input
    ref="soundtrackUploadInput"
    type="file"
    accept="audio/*,.flac,.opus"
    multiple
    class="r-v2-media__file-input"
    :aria-label="t('rom.upload-soundtrack')"
    @change="onSoundtrackUpload"
  />
  <input
    ref="screenshotUploadInput"
    type="file"
    accept="image/*"
    multiple
    class="r-v2-media__file-input"
    :aria-label="t('rom.upload-screenshots')"
    @change="onScreenshotUpload"
  />

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
                  @click="triggerManualUpload"
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
                  @click="triggerSoundtrackUpload"
                >
                  {{ t("common.upload") }}
                </RBtn>
              </template>

              <template
                v-else-if="
                  tab.id === 'screenshots' &&
                  screenshotsSupported &&
                  userScreenshots.length > 0
                "
              >
                <RBtn
                  variant="outlined"
                  prepend-icon="mdi-cloud-upload-outline"
                  block
                  @click="triggerScreenshotUpload"
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
      <section
        v-show="subTab === 'manual'"
        ref="manualPanelRef"
        class="r-v2-media__panel"
      >
        <div
          v-show="isOverManualDrop && manualEntries.length > 0"
          class="r-v2-media__drop"
          aria-hidden="true"
        >
          <RIcon icon="mdi-cloud-upload" size="40" color="primary" />
          <span class="r-v2-media__drop-label">{{
            t("common.dropzone-drag-over")
          }}</span>
        </div>

        <div
          v-if="manualEntries.length === 0"
          class="r-v2-media__dz"
          :class="{ 'r-v2-media__dz--active': isOverManualDrop }"
          role="button"
          tabindex="0"
          @click="triggerManualUpload"
          @keydown.enter.prevent="triggerManualUpload"
          @keydown.space.prevent="triggerManualUpload"
        >
          <RIcon
            :icon="
              isOverManualDrop ? 'mdi-cloud-upload' : 'mdi-cloud-upload-outline'
            "
            size="44"
            color="primary"
            :class="{ 'r-v2-media__dz-icon--pulse': isOverManualDrop }"
          />
          <h3 class="r-v2-media__dz-title">{{ t("rom.manual-empty") }}</h3>
          <p class="r-v2-media__dz-hint">{{ t("common.dropzone-hint") }}</p>
          <div class="r-v2-media__dz-actions">
            <RBtn
              color="primary"
              prepend-icon="mdi-cloud-upload-outline"
              @click.stop="triggerManualUpload"
            >
              {{ t("rom.upload-manual") }}
            </RBtn>
            <RBtn
              v-if="rom.url_manual"
              variant="outlined"
              prepend-icon="mdi-cloud-download-outline"
              :loading="redownloadingManual"
              :disabled="redownloadingManual"
              @click.stop="redownloadManual"
            >
              {{ t("rom.redownload") }}
            </RBtn>
          </div>
        </div>

        <div v-else class="r-v2-media__viewer">
          <PdfViewer
            v-if="selectedManual"
            :key="`${selectedManual.id}-${rom.updated_at}`"
            :pdf-url="selectedManual.url"
          />
        </div>
      </section>

      <!-- Soundtrack subtab -->
      <section
        v-show="subTab === 'soundtrack'"
        ref="soundtrackPanelRef"
        class="r-v2-media__panel"
      >
        <div
          v-show="
            isOverSoundtrackDrop && soundtrackSupported && rom.has_soundtrack
          "
          class="r-v2-media__drop"
          aria-hidden="true"
        >
          <RIcon icon="mdi-cloud-upload" size="40" color="primary" />
          <span class="r-v2-media__drop-label">{{
            t("common.dropzone-drag-over")
          }}</span>
        </div>

        <REmptyState
          v-if="!soundtrackSupported"
          icon="mdi-music-off"
          :title="t('rom.soundtrack-no-folder')"
          :hint="t('rom.soundtrack-folder-hint')"
        />

        <div
          v-else-if="!rom.has_soundtrack"
          class="r-v2-media__dz"
          :class="{ 'r-v2-media__dz--active': isOverSoundtrackDrop }"
          role="button"
          tabindex="0"
          @click="triggerSoundtrackUpload"
          @keydown.enter.prevent="triggerSoundtrackUpload"
          @keydown.space.prevent="triggerSoundtrackUpload"
        >
          <RIcon
            :icon="
              isOverSoundtrackDrop
                ? 'mdi-cloud-upload'
                : 'mdi-cloud-upload-outline'
            "
            size="44"
            color="primary"
            :class="{ 'r-v2-media__dz-icon--pulse': isOverSoundtrackDrop }"
          />
          <h3 class="r-v2-media__dz-title">{{ t("rom.soundtrack-empty") }}</h3>
          <p class="r-v2-media__dz-hint">{{ t("common.dropzone-hint") }}</p>
          <div class="r-v2-media__dz-actions">
            <RBtn
              color="primary"
              prepend-icon="mdi-cloud-upload-outline"
              @click.stop="triggerSoundtrackUpload"
            >
              {{ t("rom.upload-soundtrack") }}
            </RBtn>
          </div>
        </div>

        <SoundtrackPanel
          v-else
          :rom="rom"
          class="r-v2-media__soundtrack"
          @upload-tracks="triggerSoundtrackUpload"
          @delete-track="deleteSoundtrack"
        />
      </section>

      <!-- Screenshots subtab — user-uploaded images stored in the ROM's
           `screenshots/` folder. Scraped screenshots are shown in the
           Overview tab. Same folder-based gating as soundtracks: the
           assets live alongside the ROM, so single-file ROMs can't host
           them. -->
      <section
        v-show="subTab === 'screenshots'"
        ref="screenshotPanelRef"
        class="r-v2-media__panel"
      >
        <div
          v-show="
            isOverScreenshotDrop &&
            screenshotsSupported &&
            userScreenshots.length > 0
          "
          class="r-v2-media__drop"
          aria-hidden="true"
        >
          <RIcon icon="mdi-cloud-upload" size="40" color="primary" />
          <span class="r-v2-media__drop-label">{{
            t("common.dropzone-drag-over")
          }}</span>
        </div>

        <REmptyState
          v-if="!screenshotsSupported"
          icon="mdi-image-off-outline"
          :title="t('rom.screenshots-no-folder')"
          :hint="t('rom.screenshots-folder-hint')"
        />

        <ScreenshotsTab
          v-else-if="userScreenshots.length > 0"
          :screenshots="userScreenshots"
          deletable
          @delete="deleteScreenshot"
        />

        <div
          v-else
          class="r-v2-media__dz"
          :class="{ 'r-v2-media__dz--active': isOverScreenshotDrop }"
          role="button"
          tabindex="0"
          @click="triggerScreenshotUpload"
          @keydown.enter.prevent="triggerScreenshotUpload"
          @keydown.space.prevent="triggerScreenshotUpload"
        >
          <RIcon
            :icon="
              isOverScreenshotDrop
                ? 'mdi-cloud-upload'
                : 'mdi-cloud-upload-outline'
            "
            size="44"
            color="primary"
            :class="{ 'r-v2-media__dz-icon--pulse': isOverScreenshotDrop }"
          />
          <h3 class="r-v2-media__dz-title">{{ t("rom.screenshots-empty") }}</h3>
          <p class="r-v2-media__dz-hint">{{ t("common.dropzone-hint") }}</p>
          <div class="r-v2-media__dz-actions">
            <RBtn
              color="primary"
              prepend-icon="mdi-cloud-upload-outline"
              @click.stop="triggerScreenshotUpload"
            >
              {{ t("rom.upload-screenshots") }}
            </RBtn>
          </div>
        </div>
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

.r-v2-media__file-input {
  display: none;
}

/* Panels — each subtab section fills the content height so its
   children (PDF viewer / soundtrack / screenshots) can stretch
   to 100% without forcing an outer scrollbar. `position: relative`
   anchors the drag-and-drop overlay to the panel. */
.r-v2-media__panel {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: var(--r-space-3);
  flex: 1;
  min-height: 0;
}

/* Drag-and-drop overlay — covers the active panel while files are dragged
   over it. Mirrors the Upload / Patcher dropzone vocabulary (dashed brand
   border, brand glow) but as an overlay so it works over existing content
   (PDF viewer, soundtrack player, screenshot grid) as well as empty states. */
.r-v2-media__drop {
  position: absolute;
  inset: 0;
  z-index: 3;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  border: 2px dashed var(--r-color-brand-primary);
  border-radius: var(--r-radius-md);
  background: color-mix(in srgb, var(--r-color-bg) 78%, transparent);
  backdrop-filter: blur(2px);
  -webkit-backdrop-filter: blur(2px);
  pointer-events: none;
  text-align: center;
}
.r-v2-media__drop-label {
  font-size: 14px;
  font-weight: var(--r-font-weight-semibold);
  color: var(--r-color-fg);
}

/* Empty-state dropzone — the always-visible drag-and-drop affordance,
   mirroring the Upload / Patcher views (dashed brand border, cloud icon,
   click-to-browse). The whole surface is clickable; inner action buttons
   stop propagation so they trigger their specific action instead. */
.r-v2-media__dz {
  flex: 1;
  min-height: 220px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 28px 16px;
  text-align: center;
  cursor: pointer;
  border: 2px dashed
    color-mix(in srgb, var(--r-color-brand-primary) 30%, transparent);
  border-radius: var(--r-radius-lg);
  background: var(--r-color-bg-elevated);
  transition:
    border-color var(--r-motion-fast) var(--r-motion-ease-out),
    background var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-v2-media__dz:hover {
  border-color: color-mix(
    in srgb,
    var(--r-color-brand-primary) 55%,
    transparent
  );
}
.r-v2-media__dz--active {
  border-color: var(--r-color-brand-primary);
  background: color-mix(in srgb, var(--r-color-brand-primary) 8%, transparent);
}
.r-v2-media__dz-title {
  margin: 6px 0 0;
  font-size: 16px;
  font-weight: var(--r-font-weight-semibold);
  color: var(--r-color-fg);
}
.r-v2-media__dz-hint {
  margin: 0;
  font-size: 13px;
  color: var(--r-color-fg-muted);
}
.r-v2-media__dz-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: center;
  margin-top: 8px;
}
.r-v2-media__dz-icon--pulse {
  animation: r-v2-media-pulse 1.4s ease-in-out infinite;
}
@keyframes r-v2-media-pulse {
  50% {
    transform: scale(1.12);
    filter: drop-shadow(
      0 0 12px color-mix(in srgb, var(--r-color-brand-primary) 60%, transparent)
    );
  }
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
