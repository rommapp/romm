<script setup lang="ts">
// Combined Manual + Soundtrack + Screenshots tab for GameDetails.
//
// Behaviour:
//   * Subtabs always rendered; empty states drive the upload CTAs
//   * Hidden file inputs handle upload — manual upload routes through
//     `showManualUploadTargetDialog` (dialog mounted in AppLayout);
//     soundtrack upload goes straight through `romApi.uploadSoundtracks`
//   * Re-download primary manual + delete manual both handled here
//   * Screenshots subtab is currently a placeholder — scraped screenshots
//     live in the Overview tab. This subtab is reserved for user-uploaded
//     screenshots, pending backend support (see TODO below).
//
// The PDF viewer + soundtrack player are reused from v1 for now.
import { RBtn, RCollapsible, REmptyState, RIcon, RSelect } from "@v2/lib";
import axios from "axios";
import type { Emitter } from "mitt";
import { computed, defineAsyncComponent, inject, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import romApi from "@/services/api/rom";
import storeRoms, { type DetailedRom } from "@/stores/roms";
import storeUpload from "@/stores/upload";
import type { Events } from "@/types/emitter";
import { FRONTEND_RESOURCES_PATH } from "@/utils";
import { useSnackbar } from "@/v2/composables/useSnackbar";

const PdfViewer = defineAsyncComponent(
  () => import("@/v2/components/GameDetails/PdfViewer.vue"),
);
const SoundtrackPanel = defineAsyncComponent(
  () => import("@/v2/components/GameDetails/SoundtrackPanel.vue"),
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
const romsStore = storeRoms();
const uploadStore = storeUpload();

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
      label: "Scraped manual",
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
const subtabDefs: SubtabDef[] = [
  { id: "manual", label: "Manual", icon: "mdi-book-open-page-variant-outline" },
  {
    id: "soundtrack",
    label: "Soundtrack",
    icon: "mdi-music-note-outline",
  },
  {
    id: "screenshots",
    label: "Screenshots",
    icon: "mdi-image-multiple-outline",
  },
];

// Whether the active subtab has any inline actions worth rendering.
// Drives the empty-panel skip so we don't paint a stray padding block.
function hasSubtabActions(id: Subtab): boolean {
  if (id === "manual") return manualEntries.value.length > 0;
  if (id === "soundtrack")
    return soundtrackSupported.value && Boolean(props.rom.has_soundtrack);
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

// TODO: wire user-uploaded screenshots to the backend. Mirror the
// soundtrack flow: hidden file input → multipart upload via a future
// `romApi.uploadScreenshots({ romId, filesToUpload })` → success
// snackbar + `refreshRom()` so newly-uploaded shots appear here. Once
// real uploads exist, render them as a grid (reuse ScreenshotsTab.vue)
// alongside the upload CTA, mirroring the manual/soundtrack panels.
async function onScreenshotUpload(event: Event) {
  const input = event.target as HTMLInputElement;
  input.value = "";
  snackbar.info("Screenshot uploads are coming soon.", {
    icon: "mdi-information-outline",
  });
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

function onManualUpload(event: Event) {
  const input = event.target as HTMLInputElement;
  const files = input.files ? Array.from(input.files) : [];
  input.value = "";
  if (files.length === 0) return;
  emitter?.emit("showManualUploadTargetDialog", { rom: props.rom, files });
}

async function onSoundtrackUpload(event: Event) {
  const input = event.target as HTMLInputElement;
  const files = input.files ? Array.from(input.files) : [];
  if (files.length === 0) return;

  const responses = await romApi.uploadSoundtracks({
    romId: props.rom.id,
    filesToUpload: files,
  });
  input.value = "";

  const successful = responses.filter((r) => r.status === "fulfilled").length;
  const failed = responses.length - successful;

  if (failed === 0) uploadStore.reset();

  if (successful > 0) {
    snackbar.success(
      `Uploaded ${successful} track${successful === 1 ? "" : "s"}${failed ? `, ${failed} failed` : ""}.`,
      { icon: "mdi-check-bold", timeout: 3000 },
    );
    await refreshRom();
  } else {
    snackbar.warning("No tracks were uploaded.", {
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
    snackbar.success("Manual re-downloaded.", { icon: "mdi-check-bold" });
  } catch (error: unknown) {
    snackbar.error(`Manual re-download failed: ${errorMessage(error)}`, {
      icon: "mdi-close-circle",
    });
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
  try {
    await romApi.removeSoundtrack({ romId: props.rom.id, fileId });
    await refreshRom();
    snackbar.success("Track removed.", { icon: "mdi-check-bold" });
  } catch (error: unknown) {
    snackbar.error(`Couldn't remove track: ${errorMessage(error)}`, {
      icon: "mdi-close-circle",
    });
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
    aria-label="Upload manual"
    @change="onManualUpload"
  />
  <input
    ref="soundtrackUploadInput"
    type="file"
    accept="audio/*,.flac,.opus"
    multiple
    class="r-v2-media__file-input"
    aria-label="Upload soundtrack"
    @change="onSoundtrackUpload"
  />
  <input
    ref="screenshotUploadInput"
    type="file"
    accept="image/*"
    multiple
    class="r-v2-media__file-input"
    aria-label="Upload screenshots"
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
          v-for="t in subtabDefs"
          :key="t.id"
          class="r-v2-media__subtab"
          :class="{ 'r-v2-media__subtab--active': subTab === t.id }"
        >
          <button
            type="button"
            role="tab"
            class="r-v2-media__subtab-btn"
            :class="{
              'r-v2-media__subtab-btn--active': subTab === t.id,
              'r-v2-media__subtab-btn--joined':
                subTab === t.id && hasSubtabActions(t.id),
            }"
            :aria-selected="subTab === t.id"
            @click="subTab = t.id"
          >
            <RIcon :icon="t.icon" size="16" />
            <span class="r-v2-media__subtab-label">{{ t.label }}</span>
          </button>

          <!-- Inline controls panel — RCollapsible drives the open/close
               animation; `attached` removes its top radius/border so it
               sits flush with the active subtab button above. -->
          <RCollapsible
            :model-value="subTab === t.id && hasSubtabActions(t.id)"
            attached
            class="r-v2-media__subtab-panel"
          >
            <div class="r-v2-media__subtab-panel-inner">
              <template v-if="t.id === 'manual' && manualEntries.length > 0">
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
                  Upload
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
                  Re-download
                </RBtn>
                <RBtn
                  v-if="selectedManual"
                  variant="outlined"
                  color="romm-red"
                  prepend-icon="mdi-delete"
                  block
                  @click="requestDeleteManual"
                >
                  Delete
                </RBtn>
              </template>

              <template
                v-else-if="
                  t.id === 'soundtrack' &&
                  soundtrackSupported &&
                  rom.has_soundtrack
                "
              >
                <RBtn
                  size="small"
                  variant="outlined"
                  prepend-icon="mdi-cloud-upload-outline"
                  block
                  @click="triggerSoundtrackUpload"
                >
                  Upload tracks
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
        <REmptyState
          v-if="manualEntries.length === 0"
          icon="mdi-book-open-page-variant-outline"
          title="No manual yet"
        >
          <template #actions>
            <RBtn
              color="primary"
              prepend-icon="mdi-cloud-upload-outline"
              @click="triggerManualUpload"
            >
              Upload manual
            </RBtn>
            <RBtn
              v-if="rom.url_manual"
              variant="outlined"
              prepend-icon="mdi-cloud-download-outline"
              :loading="redownloadingManual"
              :disabled="redownloadingManual"
              @click="redownloadManual"
            >
              Re-download
            </RBtn>
          </template>
        </REmptyState>

        <div v-else class="r-v2-media__viewer">
          <PdfViewer
            v-if="selectedManual"
            :key="`${selectedManual.id}-${rom.updated_at}`"
            :pdf-url="selectedManual.url"
          />
        </div>
      </section>

      <!-- Soundtrack subtab -->
      <section v-show="subTab === 'soundtrack'" class="r-v2-media__panel">
        <REmptyState
          v-if="!soundtrackSupported"
          icon="mdi-music-off"
          title="Soundtrack needs a folder-based ROM"
          hint="Single-file ROMs can't have accompanying tracks. Re-organise this ROM as a folder and the upload option will appear here."
        />

        <REmptyState
          v-else-if="!rom.has_soundtrack"
          icon="mdi-music-note-outline"
          title="No soundtrack yet"
        >
          <template #actions>
            <RBtn
              color="primary"
              prepend-icon="mdi-cloud-upload-outline"
              @click="triggerSoundtrackUpload"
            >
              Upload soundtrack
            </RBtn>
          </template>
        </REmptyState>

        <SoundtrackPanel
          v-else
          :rom="rom"
          class="r-v2-media__soundtrack"
          @upload-tracks="triggerSoundtrackUpload"
          @delete-track="deleteSoundtrack"
        />
      </section>

      <!-- Screenshots subtab — placeholder until user uploads land.
           Scraped screenshots are shown in the Overview tab; this slot
           is reserved for player-captured shots once the backend
           supports them (see TODO on `onScreenshotUpload`).
           Same folder-based gating as soundtracks: user-uploaded
           assets live alongside the ROM, so single-file ROMs can't
           host them. -->
      <section v-show="subTab === 'screenshots'" class="r-v2-media__panel">
        <REmptyState
          v-if="rom.has_simple_single_file"
          icon="mdi-image-off-outline"
          title="Screenshots need a folder-based ROM"
          hint="Single-file ROMs can't have accompanying screenshots. Re-organise this ROM as a folder and the upload option will appear here."
        />

        <REmptyState
          v-else
          icon="mdi-image-multiple-outline"
          title="Upload your own screenshots"
          hint="Capture and keep your favourite moments here. Backend support is on the way."
        >
          <template #actions>
            <RBtn
              color="primary"
              prepend-icon="mdi-cloud-upload-outline"
              @click="triggerScreenshotUpload"
            >
              Upload screenshots
            </RBtn>
          </template>
        </REmptyState>
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
   to 100% without forcing an outer scrollbar. */
.r-v2-media__panel {
  display: flex;
  flex-direction: column;
  gap: var(--r-space-3);
  flex: 1;
  min-height: 0;
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
