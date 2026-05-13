<script setup lang="ts">
// EditRomDialog — v2 chrome around the ROM-edit form. Cover actions and
// metadata expansion panels keep pulling from v1 components (GameCard +
// AdditionalDetails / MetadataIdSection / MetadataSections) because those
// are deep domain composites — rebuilding them natively is a separate
// effort. The inline confirm-delete-manual and upload-target dialogs from
// v1 are gone; those flows route through the global v2
// DeleteManualDialog / ManualUploadTargetDialog via the emitter.
import { RBtn, RDialog, RIcon, RTextField } from "@v2/lib";
import type { Emitter } from "mitt";
import { computed, inject, onBeforeUnmount, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute } from "vue-router";
import { useDisplay } from "vuetify";
import GameCard from "@/components/common/Game/Card/Base.vue";
import AdditionalDetails from "@/components/common/Game/Dialog/EditRom/AdditionalDetails.vue";
import MetadataIdSection from "@/components/common/Game/Dialog/EditRom/MetadataIdSection.vue";
import MetadataSections from "@/components/common/Game/Dialog/EditRom/MetadataSections.vue";
import romApi, { type UpdateRom } from "@/services/api/rom";
import storeHeartbeat from "@/stores/heartbeat";
import storeRoms, { type DetailedRom, type SimpleRom } from "@/stores/roms";
import storeUpload from "@/stores/upload";
import type { Events } from "@/types/emitter";
import { formatBytes } from "@/utils";
import { getMissingCoverImage } from "@/utils/covers";
import { useSnackbar } from "@/v2/composables/useSnackbar";

defineOptions({ inheritAttrs: false });

const { t } = useI18n();
const { lgAndUp } = useDisplay();
const heartbeat = storeHeartbeat();
const route = useRoute();
const show = ref(false);
// `UpdateRom = SimpleRom & {...}` but we need DetailedRom for delegating
// manual/upload flows to global v2 dialogs. We hold a DetailedRom-compatible
// shape internally and widen at edit/emit boundaries.
type EditableRom = DetailedRom & UpdateRom;
const rom = ref<EditableRom | null>(null);
const romsStore = storeRoms();
const imagePreviewUrl = ref<string | undefined>("");
const removeCover = ref(false);
const manualFiles = ref<File[]>([]);
const soundtrackFiles = ref<File[]>([]);
const uploadStore = storeUpload();
const coverFileInput = ref<HTMLInputElement | null>(null);
const manualFileInput = ref<HTMLInputElement | null>(null);
const soundtrackFileInput = ref<HTMLInputElement | null>(null);
const emitter = inject<Emitter<Events>>("emitter");
const snackbar = useSnackbar();

const soundtrackTracks = computed(
  () =>
    rom.value?.files
      ?.filter((f) => f.category === "soundtrack")
      .slice()
      .sort((a, b) => a.file_name.localeCompare(b.file_name)) ?? [],
);

const openHandler = async (romToEdit: SimpleRom) => {
  show.value = true;
  // Show the simple rom immediately so the dialog mounts; fetch the
  // detailed version in the background so manual/soundtrack flows that
  // rely on file arrays have real data.
  rom.value = romToEdit as EditableRom;
  removeCover.value = false;
  imagePreviewUrl.value = "";
  try {
    const { data } = await romApi.getRom({ romId: romToEdit.id });
    if (show.value) rom.value = data as EditableRom;
  } catch (error) {
    console.error("Failed to fetch detailed rom", error);
  }
};
emitter?.on("showEditRomDialog", openHandler);

const urlCoverHandler = (url_cover: string) => setUrlCover(url_cover);
emitter?.on("updateUrlCover", urlCoverHandler);

onBeforeUnmount(() => {
  emitter?.off("showEditRomDialog", openHandler);
  emitter?.off("updateUrlCover", urlCoverHandler);
});

const missingCoverImage = computed(() =>
  getMissingCoverImage(rom.value?.name || rom.value?.fs_name || ""),
);

const validForm = computed(() => !!(rom.value?.name && rom.value?.fs_name));

function previewImage(event: Event) {
  if (!rom.value) return;
  const input = event.target as HTMLInputElement;
  if (!input.files || !input.files[0]) return;

  rom.value.artwork = input.files[0];
  const reader = new FileReader();
  reader.onload = () => {
    imagePreviewUrl.value = reader.result?.toString() || "";
    removeCover.value = false;
  };
  reader.readAsDataURL(input.files[0]);
}

function setUrlCover(coverUrl: string) {
  if (!coverUrl || !rom.value) return;
  rom.value.url_cover = coverUrl;
  imagePreviewUrl.value = coverUrl;
  removeCover.value = false;
}

function removeArtwork() {
  imagePreviewUrl.value = missingCoverImage.value;
  removeCover.value = true;
}

async function handleRomUpdate(
  options: { rom: UpdateRom; removeCover?: boolean; unmatch?: boolean },
  successMessage: string,
) {
  emitter?.emit("showLoadingDialog", { loading: true, scrim: true });
  try {
    const { data } = await romApi.updateRom(options);
    snackbar.success(successMessage, { icon: "mdi-check-bold" });
    romsStore.update(data as SimpleRom);
    if (route.name === "rom") romsStore.currentRom = data;
  } catch (error: unknown) {
    console.error(error);
    const axiosErr = error as { response?: { data?: { detail?: string } } };
    snackbar.error(axiosErr.response?.data?.detail ?? "Update failed", {
      icon: "mdi-close-circle",
    });
  } finally {
    emitter?.emit("showLoadingDialog", { loading: false, scrim: false });
    closeDialog();
  }
}

function uploadManuals() {
  if (!rom.value || manualFiles.value.length === 0) return;
  const files = [...manualFiles.value];
  manualFiles.value = [];
  // Route through the global v2 ManualUploadTargetDialog so the
  // resources/folder picker lives in one place. If the ROM is a simple
  // single-file ROM the dialog skips the prompt and defaults to resources.
  emitter?.emit("showManualUploadTargetDialog", { rom: rom.value, files });
}

function confirmRemoveManual() {
  if (!rom.value) return;
  emitter?.emit("showDeleteManualDialog", {
    rom: rom.value,
    isPrimary: true,
    fileId: undefined,
  });
}

async function uploadSoundtracks() {
  if (!rom.value) return;
  try {
    const responses = await romApi.uploadSoundtracks({
      romId: rom.value.id,
      filesToUpload: soundtrackFiles.value,
    });
    const successful = responses.filter((d) => d.status === "fulfilled");
    const failed = responses.filter((d) => d.status === "rejected");
    if (failed.length === 0) uploadStore.reset();

    if (successful.length === 0) {
      snackbar.warning(t("rom.soundtracks-upload-skipped"), {
        icon: "mdi-close-circle",
        timeout: 5000,
      });
    } else {
      snackbar.success(
        t("rom.soundtracks-upload-success", {
          count: successful.length,
          failed: failed.length,
        }),
        { icon: "mdi-check-bold", timeout: 3000 },
      );
      await refreshRomState();
    }
  } catch (error: unknown) {
    const axiosErr = error as {
      response?: { data?: { detail?: string }; statusText?: string };
      message?: string;
    };
    snackbar.error(
      t("rom.soundtracks-upload-failed", {
        error:
          axiosErr.response?.data?.detail ??
          axiosErr.response?.statusText ??
          axiosErr.message,
      }),
      { icon: "mdi-close-circle", timeout: 4000 },
    );
  }
  soundtrackFiles.value = [];
}

async function removeSoundtrack(fileId: number) {
  if (!rom.value) return;
  try {
    await romApi.removeSoundtrack({ romId: rom.value.id, fileId });
    await refreshRomState();
    snackbar.success(t("rom.soundtrack-removed"), { icon: "mdi-check-bold" });
  } catch (error: unknown) {
    const axiosErr = error as {
      response?: { data?: { detail?: string } };
      message?: string;
    };
    snackbar.error(
      t("rom.soundtrack-remove-failed", {
        error: axiosErr.response?.data?.detail ?? axiosErr.message,
      }),
      { icon: "mdi-close-circle" },
    );
  }
}

async function refreshRomState() {
  if (!rom.value) return;
  const { data } = await romApi.getRom({ romId: rom.value.id });
  rom.value = data as EditableRom;
  romsStore.update(data as SimpleRom);
  if (route.name === "rom") romsStore.currentRom = data;
}

async function unmatchRom() {
  if (!rom.value) return;
  await handleRomUpdate(
    { rom: rom.value, unmatch: true },
    t("rom.unmatch-success"),
  );
}

async function updateRom() {
  if (!rom.value?.fs_name) {
    snackbar.error(t("rom.filename-required"), { icon: "mdi-close-circle" });
    return;
  }
  await handleRomUpdate(
    { rom: rom.value, removeCover: removeCover.value },
    t("rom.update-success"),
  );
}

function closeDialog() {
  show.value = false;
  rom.value = null;
  imagePreviewUrl.value = "";
}

function handleRomUpdateFromMetadata(updatedRom: UpdateRom) {
  rom.value = updatedRom as EditableRom;
}
</script>

<template>
  <RDialog
    v-if="rom"
    v-model="show"
    icon="mdi-pencil-box"
    scroll-content
    :width="lgAndUp ? 900 : '95vw'"
    @close="closeDialog"
  >
    <template #header>
      <span>{{ t("rom.edit-rom", "Edit ROM") }}</span>
    </template>

    <template #content>
      <div class="r-v2-edit">
        <!-- Cover column -->
        <div class="r-v2-edit__cover-col">
          <GameCard
            width="220"
            :rom="rom"
            :cover-src="imagePreviewUrl"
            disable-view-transition
            :show-platform-icon="false"
            :show-action-bar="false"
            force-boxart="cover_path"
          />
          <div class="r-v2-edit__cover-actions">
            <button
              type="button"
              class="r-v2-edit__icon-btn"
              :disabled="
                !heartbeat.value.METADATA_SOURCES?.STEAMGRIDDB_API_ENABLED
              "
              :title="t('rom.search-cover', 'Search cover')"
              @click="
                emitter?.emit('showSearchCoverDialog', {
                  term: rom.name || rom.fs_name,
                  platformId: rom.platform_id,
                })
              "
            >
              <RIcon icon="mdi-image-search-outline" size="16" />
            </button>
            <button
              type="button"
              class="r-v2-edit__icon-btn"
              :title="t('rom.upload-cover', 'Upload cover')"
              @click="coverFileInput?.click()"
            >
              <RIcon icon="mdi-pencil" size="16" />
            </button>
            <input
              ref="coverFileInput"
              type="file"
              accept="image/*"
              :aria-label="t('rom.upload-cover', 'Upload cover')"
              class="r-v2-edit__file"
              @change="previewImage"
            />
            <button
              type="button"
              class="r-v2-edit__icon-btn r-v2-edit__icon-btn--danger"
              :title="t('rom.remove-cover', 'Remove cover')"
              @click="removeArtwork"
            >
              <RIcon icon="mdi-delete" size="16" />
            </button>
          </div>
        </div>

        <!-- Form column -->
        <div class="r-v2-edit__form-col">
          <RTextField
            v-model="rom.name"
            prefix-label="stacked"
            hide-details
            :rules="[(v: string) => !!v || t('common.required')]"
          >
            <template #prefix-label>
              <RIcon icon="mdi-format-title" size="14" />
              {{ t("common.name") }}
            </template>
          </RTextField>
          <RTextField
            v-model="rom.fs_name"
            prefix-label="stacked"
            hide-details
            :rules="[(v: string) => !!v || t('common.required')]"
          >
            <template #prefix-label>
              <RIcon
                :icon="
                  rom.has_nested_single_file || rom.has_multiple_files
                    ? 'mdi-folder-outline'
                    : 'mdi-file-outline'
                "
                size="14"
              />
              {{
                rom.has_nested_single_file || rom.has_multiple_files
                  ? t("rom.folder-name")
                  : t("rom.filename")
              }}
            </template>
          </RTextField>
          <p class="r-v2-edit__path">
            <RIcon icon="mdi-folder-file-outline" size="13" />
            /romm/library/{{ rom.fs_path }}/{{ rom.fs_name }}
          </p>

          <RTextField v-model="rom.summary" prefix-label="stacked" hide-details>
            <template #prefix-label>
              <RIcon icon="mdi-text" size="14" />
              {{ t("rom.summary") }}
            </template>
          </RTextField>

          <!-- Manual -->
          <div class="r-v2-edit__row">
            <div
              class="r-v2-edit__badge"
              :class="{ 'r-v2-edit__badge--ok': rom.has_manual }"
            >
              <RIcon
                :icon="rom.has_manual ? 'mdi-check' : 'mdi-close'"
                size="12"
              />
              {{ t("rom.manual") }}
            </div>
            <button
              type="button"
              class="r-v2-edit__icon-btn"
              :title="t('rom.upload-manual', 'Upload manual')"
              @click="manualFileInput?.click()"
            >
              <RIcon icon="mdi-cloud-upload-outline" size="16" />
            </button>
            <input
              ref="manualFileInput"
              type="file"
              accept="application/pdf"
              multiple
              :aria-label="t('rom.upload-manual', 'Upload manual')"
              class="r-v2-edit__file"
              @change="
                ($event) => {
                  const target = $event.target as HTMLInputElement;
                  if (target.files) manualFiles = Array.from(target.files);
                  uploadManuals();
                  target.value = '';
                }
              "
            />
            <button
              v-if="rom.has_manual"
              type="button"
              class="r-v2-edit__icon-btn r-v2-edit__icon-btn--danger"
              :title="t('rom.delete-manual-button')"
              @click="confirmRemoveManual"
            >
              <RIcon icon="mdi-delete" size="16" />
            </button>
            <div style="flex: 1" />
            <RBtn
              variant="outlined"
              size="small"
              color="error"
              :disabled="rom.is_unidentified"
              @click="unmatchRom"
            >
              {{ t("rom.unmatch") }}
            </RBtn>
          </div>
          <p v-if="rom.has_manual" class="r-v2-edit__path">
            <RIcon icon="mdi-folder-file-outline" size="13" />
            /romm/resources/{{ rom.path_manual }}
          </p>

          <!-- Soundtrack -->
          <div class="r-v2-edit__row">
            <div
              class="r-v2-edit__badge"
              :class="{ 'r-v2-edit__badge--ok': rom.has_soundtrack }"
            >
              <RIcon
                :icon="rom.has_soundtrack ? 'mdi-check' : 'mdi-close'"
                size="12"
              />
              {{ t("rom.soundtrack") }}
            </div>
            <button
              type="button"
              class="r-v2-edit__icon-btn"
              :title="t('rom.upload-soundtrack', 'Upload soundtrack')"
              :disabled="rom.has_simple_single_file"
              @click="soundtrackFileInput?.click()"
            >
              <RIcon icon="mdi-cloud-upload-outline" size="16" />
            </button>
            <input
              ref="soundtrackFileInput"
              type="file"
              accept="audio/*,.flac,.opus"
              multiple
              :aria-label="t('rom.upload-soundtrack', 'Upload soundtrack')"
              class="r-v2-edit__file"
              @change="
                ($event) => {
                  const target = $event.target as HTMLInputElement;
                  if (target.files) soundtrackFiles = Array.from(target.files);
                  uploadSoundtracks();
                  target.value = '';
                }
              "
            />
            <span v-if="rom.has_simple_single_file" class="r-v2-edit__hint">
              {{ t("rom.soundtrack-folder-only") }}
            </span>
          </div>

          <ul v-if="soundtrackTracks.length > 0" class="r-v2-edit__tracks">
            <li
              v-for="track in soundtrackTracks"
              :key="track.id"
              class="r-v2-edit__track"
            >
              <RIcon icon="mdi-music-note" size="14" />
              <span class="r-v2-edit__track-name" :title="track.file_name">
                {{ track.file_name }}
              </span>
              <span class="r-v2-edit__track-size">
                {{ formatBytes(track.file_size_bytes) }}
              </span>
              <button
                type="button"
                class="r-v2-edit__icon-btn r-v2-edit__icon-btn--danger r-v2-edit__icon-btn--xs"
                :title="t('rom.soundtrack-removed', 'Remove track')"
                @click="removeSoundtrack(track.id)"
              >
                <RIcon icon="mdi-delete" size="13" />
              </button>
            </li>
          </ul>
        </div>
      </div>

      <!-- Metadata expansion panels (v1 composites — scope for a future polish). -->
      <v-expansion-panels class="r-v2-edit__panels" variant="accordion">
        <AdditionalDetails
          :rom="rom"
          @update:rom="handleRomUpdateFromMetadata"
        />
        <MetadataIdSection
          :rom="rom"
          @update:rom="handleRomUpdateFromMetadata"
        />
        <MetadataSections
          :rom="rom"
          @update:rom="handleRomUpdateFromMetadata"
        />
      </v-expansion-panels>
    </template>

    <template #footer>
      <RBtn variant="text" @click="closeDialog">
        {{ t("common.cancel") }}
      </RBtn>
      <div style="flex: 1" />
      <RBtn
        variant="translucent"
        color="primary"
        prepend-icon="mdi-check"
        :disabled="!validForm"
        @click="updateRom"
      >
        {{ t("common.apply") }}
      </RBtn>
    </template>
  </RDialog>
</template>

<style scoped>
.r-v2-edit {
  display: grid;
  grid-template-columns: 220px 1fr;
  gap: 18px;
  align-items: start;
}

.r-v2-edit__cover-col {
  display: flex;
  flex-direction: column;
  gap: 8px;
  align-items: center;
}

.r-v2-edit__cover-actions {
  display: flex;
  gap: 4px;
}

.r-v2-edit__icon-btn {
  appearance: none;
  background: var(--r-color-surface);
  border: 1px solid var(--r-color-border-strong);
  color: var(--r-color-fg-secondary);
  width: 32px;
  height: 32px;
  border-radius: var(--r-radius-sm);
  display: grid;
  place-items: center;
  cursor: pointer;
  transition:
    background var(--r-motion-fast) var(--r-motion-ease-out),
    color var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-v2-edit__icon-btn:hover:not(:disabled) {
  background: var(--r-color-surface-hover);
  color: var(--r-color-fg);
}
.r-v2-edit__icon-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.r-v2-edit__icon-btn--danger:hover:not(:disabled) {
  background: color-mix(
    in srgb,
    var(--r-color-status-base-danger) 18%,
    transparent
  );
  color: var(--r-color-danger-fg);
}
.r-v2-edit__icon-btn--xs {
  width: 24px;
  height: 24px;
}

.r-v2-edit__file {
  position: absolute;
  width: 0;
  height: 0;
  opacity: 0;
  pointer-events: none;
}

.r-v2-edit__form-col {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-width: 0;
}

.r-v2-edit__path {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin: -4px 0 0;
  font-size: 11px;
  color: var(--r-color-fg-muted);
  font-family: var(--r-font-family-mono, monospace);
  word-break: break-all;
}
.r-v2-edit__path :deep(.r-icon) {
  color: var(--r-color-brand-primary);
  flex-shrink: 0;
}

.r-v2-edit__row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 4px;
  flex-wrap: wrap;
}

.r-v2-edit__badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: var(--r-radius-pill);
  background: color-mix(
    in srgb,
    var(--r-color-status-base-danger) 12%,
    transparent
  );
  border: 1px solid
    color-mix(in srgb, var(--r-color-status-base-danger) 25%, transparent);
  color: var(--r-color-danger-fg);
  font-size: 12px;
  font-weight: var(--r-font-weight-medium);
}
.r-v2-edit__badge--ok {
  background: color-mix(
    in srgb,
    var(--r-color-status-base-success) 14%,
    transparent
  );
  border-color: color-mix(
    in srgb,
    var(--r-color-status-base-success) 30%,
    transparent
  );
  color: var(--r-color-success);
}

.r-v2-edit__hint {
  font-size: 11px;
  color: var(--r-color-fg-muted);
}

.r-v2-edit__tracks {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.r-v2-edit__track {
  display: grid;
  grid-template-columns: auto 1fr auto auto;
  gap: 8px;
  align-items: center;
  padding: 6px 10px;
  background: var(--r-color-bg-elevated);
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-sm);
  font-size: 12px;
}
.r-v2-edit__track-name {
  color: var(--r-color-fg);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  min-width: 0;
}
.r-v2-edit__track-size {
  font-size: 11px;
  color: var(--r-color-fg-muted);
  font-variant-numeric: tabular-nums;
}

.r-v2-edit__panels {
  margin-top: 18px;
}

@media (max-width: 820px) {
  .r-v2-edit {
    grid-template-columns: 1fr;
  }
  .r-v2-edit__cover-col {
    max-width: 220px;
    margin: 0 auto;
  }
}
</style>
