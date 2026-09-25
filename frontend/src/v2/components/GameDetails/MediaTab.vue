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
//   * Upload goes through `useRomFileUpload`, into the soundtrack/ folder
//   * A disc (cue sheet or CHD) can extract its CD audio tracks there too
//
// The soundtrack player is reused from v1 for now.
import { RBtn, RDropzone, REmptyState } from "@v2/lib";
import { computed, defineAsyncComponent, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import romApi from "@/services/api/rom";
import type { DetailedRom } from "@/stores/roms";
import SubtabNav, {
  type SubtabNavItem,
} from "@/v2/components/GameDetails/SubtabNav.vue";
import { useBreakpoint } from "@/v2/composables/useBreakpoint";
import { useCan } from "@/v2/composables/useCan";
import { useIsAlive } from "@/v2/composables/useIsAlive";
import {
  ROM_UPLOAD_FOLDERS,
  useRomFileUpload,
} from "@/v2/composables/useRomFileUpload";
import { useRomSoundtrack } from "@/v2/composables/useRomSoundtrack";
import { useRomSync } from "@/v2/composables/useRomSync";
import { useSnackbar } from "@/v2/composables/useSnackbar";
import { useSoundtrackActions } from "@/v2/composables/useSoundtrackActions";
import { useSubtabQuery } from "@/v2/composables/useSubtabQuery";
import { errorMessage } from "@/v2/utils/errorMessage";
import { hasDiscImage } from "@/v2/utils/romFiles";

const ManualSubtab = defineAsyncComponent(
  () => import("@/v2/components/GameDetails/ManualSubtab.vue"),
);
const WalkthroughSubtab = defineAsyncComponent(
  () => import("@/v2/components/GameDetails/WalkthroughSubtab.vue"),
);
const SoundtrackPanel = defineAsyncComponent(
  () => import("@/v2/components/Soundtrack/Panel.vue"),
);
const ScreenshotsSubtab = defineAsyncComponent(
  () => import("@/v2/components/GameDetails/ScreenshotsSubtab.vue"),
);
const ArtworkSubtab = defineAsyncComponent(
  () => import("@/v2/components/GameDetails/ArtworkSubtab.vue"),
);

const props = defineProps<{ rom: DetailedRom }>();
const soundtrackActions = useSoundtrackActions();
const { uploadFiles } = useRomFileUpload();
const {
  tracks: soundtrackTracks,
  loading: soundtrackLoading,
  fallbackArtUrl: soundtrackArtUrl,
} = useRomSoundtrack(() => props.rom);
const { refetchRom } = useRomSync();
const snackbar = useSnackbar();
const { t } = useI18n();
const { smAndDown } = useBreakpoint();

// Soundtrack upload / delete both gate on the ROM write grant, so read-only
// users get the player without any upload or delete affordance.
const canEdit = useCan("rom.edit");

// ---------- Subtab state ----------
// Mirrored to `?subtab=` so the SoundtrackMiniPlayer can detect when the full
// player is visible here and hide itself to avoid duplication.
const validSubtabs = [
  "manual",
  "walkthrough",
  "screenshots",
  "artwork",
  "soundtrack",
] as const;
type Subtab = (typeof validSubtabs)[number];

const subTab = useSubtabQuery<Subtab>(
  "media",
  (value) => validSubtabs.includes(value as Subtab),
  "manual",
);

// ---------- Subtab nav ----------
const subtabDefs = computed<SubtabNavItem<Subtab>[]>(() => [
  {
    id: "manual",
    label: t("rom.manual"),
    icon: "mdi-book-open-page-variant-outline",
  },
  {
    id: "walkthrough",
    label: t("rom.walkthrough"),
    icon: "mdi-map-legend",
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
const canUploadSoundtrack = computed(
  () => props.rom.has_soundtrack && canEdit.value,
);
// Probed when the subtab opens, and again whenever the ROM's files change, so
// the action only shows while the disc has audio tracks left to extract.
const cdAudioProbeKey = computed(() =>
  subTab.value === "soundtrack" && canEdit.value && hasDiscImage(props.rom)
    ? `${props.rom.id}:${(props.rom.files ?? [])
        .map((f) => `${f.id}@${f.updated_at}`)
        .join(",")}`
    : null,
);
const pendingCdAudioTracks = ref(0);
const alive = useIsAlive();
watch(
  cdAudioProbeKey,
  async (key) => {
    pendingCdAudioTracks.value = 0;
    if (!key) return;
    try {
      const { data } = await romApi.getCdAudioStatus({ romId: props.rom.id });
      if (alive.value && cdAudioProbeKey.value === key) {
        pendingCdAudioTracks.value = data.tracks - data.extracted;
      }
    } catch {
      // An unreadable disc just offers nothing to extract.
    }
  },
  { immediate: true },
);
const canExtractCdAudio = computed(() => pendingCdAudioTracks.value > 0);
const extractingCdAudio = ref(false);

// On phones a subtab's single Upload joins the picker row; Screenshots has one
// per section, so it keeps them in place.
const manualPanel = ref<InstanceType<typeof ManualSubtab> | null>(null);
const walkthroughPanel = ref<InstanceType<typeof WalkthroughSubtab> | null>(
  null,
);

const pickerRowUpload = computed<(() => void) | null>(() => {
  switch (subTab.value) {
    case "manual":
      return manualPanel.value?.canUpload ? manualPanel.value.openUpload : null;
    case "walkthrough":
      return walkthroughPanel.value?.canUpload
        ? walkthroughPanel.value.openUpload
        : null;
    case "soundtrack":
      return canUploadSoundtrack.value
        ? () => soundtrackDz.value?.open()
        : null;
    default:
      return null;
  }
});

async function refreshRom() {
  await refetchRom(props.rom.id);
}

// ---------- File handlers (shared by file input + drag-and-drop) ----------
async function handleSoundtrackFiles(files: File[]) {
  await uploadFiles(props.rom, ROM_UPLOAD_FOLDERS.soundtrack, files);
}

async function extractCdAudio() {
  // RBtn's loading state doesn't disable it, so a double click would re-run.
  if (extractingCdAudio.value) return;
  const romId = props.rom.id;
  extractingCdAudio.value = true;
  try {
    const { data } = await romApi.extractCdAudio({ romId });
    if (data.extracted.length > 0) {
      snackbar.success(
        t("rom.soundtrack-cd-audio-extracted", data.extracted.length),
      );
      await refetchRom(romId);
    } else if (data.skipped.length > 0) {
      snackbar.info(t("rom.soundtrack-cd-audio-up-to-date"));
    } else {
      snackbar.info(t("rom.soundtrack-cd-audio-none"));
    }
  } catch (error: unknown) {
    snackbar.error(
      t("rom.soundtrack-cd-audio-failed", { error: errorMessage(error) }),
    );
  } finally {
    extractingCdAudio.value = false;
  }
}

async function deleteSoundtrack(fileId: number) {
  const track = (props.rom.files ?? []).find((f) => f.id === fileId);
  if (
    await soundtrackActions.deleteTrack(props.rom.id, fileId, track?.file_name)
  ) {
    await refreshRom();
  }
}
</script>

<template>
  <div class="r-v2-media">
    <SubtabNav
      v-if="smAndDown"
      v-model="subTab"
      :items="subtabDefs"
      variant="menu"
    >
      <template #actions>
        <!-- Icon-only, so the subtab picker keeps room for its label. -->
        <RBtn
          v-if="subTab === 'soundtrack' && canExtractCdAudio"
          icon="mdi-disc"
          variant="outlined"
          size="small"
          density="comfortable"
          :tooltip="t('rom.soundtrack-extract-cd-audio')"
          :aria-label="t('rom.soundtrack-extract-cd-audio')"
          :loading="extractingCdAudio"
          @click="extractCdAudio"
        />
        <RBtn
          v-if="pickerRowUpload"
          variant="outlined"
          size="small"
          density="comfortable"
          prepend-icon="mdi-cloud-upload-outline"
          @click="pickerRowUpload()"
        >
          {{ t("common.upload") }}
        </RBtn>
      </template>
    </SubtabNav>
    <aside v-else class="r-v2-media__sidebar">
      <SubtabNav v-model="subTab" :items="subtabDefs" />
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
        <ManualSubtab ref="manualPanel" :rom="rom" :hide-upload="smAndDown" />
      </section>

      <!-- Walkthrough subtab: uploaded or GameFAQs-fetched documents, with
           per-user reading progress. -->
      <section v-show="subTab === 'walkthrough'" class="r-v2-media__panel">
        <WalkthroughSubtab
          ref="walkthroughPanel"
          :rom="rom"
          :hide-upload="smAndDown"
        />
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
        <header
          v-if="(canUploadSoundtrack || canExtractCdAudio) && !smAndDown"
          class="r-v2-media__section-head"
        >
          <div class="r-v2-media__section-actions">
            <RBtn
              v-if="canExtractCdAudio"
              variant="outlined"
              size="small"
              prepend-icon="mdi-disc"
              :loading="extractingCdAudio"
              @click="extractCdAudio"
            >
              {{ t("rom.soundtrack-extract-cd-audio") }}
            </RBtn>
            <RBtn
              v-if="canUploadSoundtrack"
              variant="outlined"
              size="small"
              prepend-icon="mdi-cloud-upload-outline"
              @click="soundtrackDz?.open()"
            >
              {{ t("common.upload") }}
            </RBtn>
          </div>
        </header>

        <REmptyState
          v-if="!rom.has_soundtrack && !canEdit"
          :title="t('rom.soundtrack-empty')"
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
          :disabled="!canEdit"
          class="r-v2-media__fill"
          :release-label="t('common.dropzone-drag-over')"
          :input-label="t('rom.upload-soundtrack')"
          accept="audio/*,.flac,.opus"
          multiple
          @files="handleSoundtrackFiles"
        >
          <SoundtrackPanel
            :tracks="soundtrackTracks"
            :playlist-key="rom.id"
            :loading="soundtrackLoading"
            :fallback-art-url="soundtrackArtUrl"
            :deletable="canEdit"
            class="r-v2-media__soundtrack"
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

/* The sidebar's subtab label already names the section, so the header skips
   the title and pushes the action cluster to the right. */
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

/* Mobile has no fixed-height chain to fill (GameDetails scrolls as one
   document there), so a zero flex-basis would collapse the player. */
html[data-bp~="sm-and-down"] .r-v2-media__fill {
  flex: none;
  height: auto;
}

html[data-bp~="sm-and-down"] .r-v2-media {
  flex-direction: column;
  gap: 14px;
}

/* Soundtrack — the v1 player has its own internal styling; wrap in an
   elevated container so it blends with v2 tokens. */
.r-v2-media__soundtrack {
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-md);
  background: var(--r-color-bg-elevated);
}
</style>
