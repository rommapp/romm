<script setup lang="ts">
// Combined Manual + Screenshots + Artwork + Soundtrack tab for GameDetails.
// This shell owns the subtab navigation (mirrored to `?subtab=`) and the
// soundtrack panel; each other subtab is its own self-contained component
// (ManualSubtab, ScreenshotsSubtab, ArtworkSubtab).
//
// Soundtrack behaviour:
//   * Subtab always rendered; the empty state drives the upload CTA
//   * The panel doubles as a drag-and-drop target (same affordance as the
//     Upload / Patcher views): drop files anywhere over it to upload
//   * Upload goes through `romApi.uploadSoundtracks`
//
// The soundtrack player is reused from v1 for now.
import { RBtn, RDropzone, RIcon } from "@v2/lib";
import axios from "axios";
import { computed, defineAsyncComponent, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute, useRouter } from "vue-router";
import romApi from "@/services/api/rom";
import storeRoms, { type DetailedRom } from "@/stores/roms";
import storeUpload from "@/stores/upload";
import { useConfirm } from "@/v2/composables/useConfirm";
import { useSnackbar } from "@/v2/composables/useSnackbar";

const ManualSubtab = defineAsyncComponent(
  () => import("@/v2/components/GameDetails/ManualSubtab.vue"),
);
const SoundtrackPanel = defineAsyncComponent(
  () => import("@/v2/components/GameDetails/SoundtrackPanel.vue"),
);
const ScreenshotsSubtab = defineAsyncComponent(
  () => import("@/v2/components/GameDetails/ScreenshotsSubtab.vue"),
);
const ArtworkSubtab = defineAsyncComponent(
  () => import("@/v2/components/GameDetails/ArtworkSubtab.vue"),
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
const snackbar = useSnackbar();
const confirm = useConfirm();
const romsStore = storeRoms();
const uploadStore = storeUpload();
const { t } = useI18n();

// ---------- Subtab state ----------
// Mirrored to `?subtab=` so the SoundtrackMiniPlayer can detect when the full
// player is visible here and hide itself to avoid duplication.
const validSubtabs = [
  "manual",
  "screenshots",
  "artwork",
  "soundtrack",
] as const;
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

// ---------- Single-file -> folder conversion ----------
// Soundtracks live inside the ROM folder, so uploading one to a single-file
// ROM promotes it to a folder ROM in place (the backend does this
// automatically on upload). Warn first since it is not reversible.
async function confirmFolderConversionIfNeeded(): Promise<boolean> {
  if (!props.rom.has_simple_single_file) return true;
  return confirm({
    title: t("rom.convert-to-folder-title"),
    body: t("rom.convert-to-folder-body"),
    tone: "warning",
  });
}

// ---------- Subtab nav ----------
// We render the subtab list manually (not via RTabNav) because each
// subtab's content panel owns its own section header with title +
// contextual actions — the sidebar stays navigation-only, mirroring
// ScreenshotsSubtab.
type SubtabDef = { id: Subtab; label: string; icon: string };
const subtabDefs = computed<SubtabDef[]>(() => [
  {
    id: "manual",
    label: t("rom.manual"),
    icon: "mdi-book-open-page-variant-outline",
  },
  {
    id: "screenshots",
    label: t("rom.screenshots"),
    icon: "mdi-image-multiple-outline",
  },
  {
    id: "artwork",
    label: t("rom.artwork"),
    icon: "mdi-palette-outline",
  },
  {
    id: "soundtrack",
    label: t("rom.soundtrack"),
    icon: "mdi-music-note-outline",
  },
]);

// ---------- Upload / refresh plumbing ----------
// The soundtrack panel uses an RDropzone (CTA when empty, overlay over the
// player when filled). The section header's "upload" button opens the filled
// dropzone's picker via this ref.
const soundtrackDz = ref<InstanceType<typeof RDropzone> | null>(null);

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
async function handleSoundtrackFiles(files: File[]) {
  if (files.length === 0) return;
  if (!(await confirmFolderConversionIfNeeded())) return;

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
            }"
            :aria-selected="subTab === tab.id"
            @click="subTab = tab.id"
          >
            <RIcon :icon="tab.icon" size="16" />
            <span class="r-v2-media__subtab-label">{{ tab.label }}</span>
          </button>
        </li>
      </ul>
    </aside>

    <div class="r-v2-media__content">
      <!-- All subtab sections stay mounted (v-show, not v-if). The manual,
           soundtrack and screenshots panels are heavy defineAsyncComponent
           loads — un/remounting them on every subtab switch causes a visible
           main-thread freeze (the PDF parser is the worst offender). With
           v-show the cost is paid once on Media tab entry and switching is a
           CSS toggle. -->
      <!-- Manual subtab — its own component (PDF / Markdown viewer with an
           entry selector; scrolls independently). -->
      <section v-show="subTab === 'manual'" class="r-v2-media__panel">
        <ManualSubtab :rom="rom" />
      </section>

      <!-- Screenshots subtab — its own component (ROM / Mine / Community
           sections, per-user public/private). -->
      <section v-show="subTab === 'screenshots'" class="r-v2-media__panel">
        <ScreenshotsSubtab :rom="rom" />
      </section>

      <!-- Artwork subtab — read-only gallery of scraped art assets
           (bezel / logo / marquee / box art / fan art / videos). -->
      <section v-show="subTab === 'artwork'" class="r-v2-media__panel">
        <ArtworkSubtab :rom="rom" />
      </section>

      <!-- Soundtrack subtab -->
      <section v-show="subTab === 'soundtrack'" class="r-v2-media__panel">
        <RDropzone
          v-if="!rom.has_soundtrack"
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
          class="r-v2-media__fill"
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

/* Subtab list — navigation only. Per-section actions (Upload, etc.)
   live in the content column's section headers, mirroring
   ScreenshotsSubtab. */
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
.r-v2-media__subtab-label {
  flex: 1;
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
   children (manual / soundtrack / screenshots) can stretch to 100%
   without forcing an outer scrollbar. */
.r-v2-media__panel {
  display: flex;
  flex-direction: column;
  gap: var(--r-space-3);
  flex: 1;
  min-height: 0;
}

/* Section header — toolbar row. The sidebar's subtab label already
   names the section, so the header skips the title and hosts the
   contextual controls only: the action cluster pushed to the right. */
.r-v2-media__section-head {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}
.r-v2-media__section-actions {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

/* Overlay-mode RDropzone wrapping the soundtrack player must fill the
   panel height so the inner player can stretch to 100%. */
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

/* Soundtrack — the v1 player has its own internal styling; wrap in an
   elevated container so it blends with v2 tokens. */
.r-v2-media__soundtrack {
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-md);
  background: var(--r-color-bg-elevated);
}
</style>
