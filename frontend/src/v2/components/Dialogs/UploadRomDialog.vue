<script setup lang="ts">
// UploadRomDialog — global emitter-driven dialog that posts ROM files
// to a chosen platform. Mounted from GlobalDialogs; the event payload
// is the pre-selected `Platform` (e.g. when triggered from
// Platform.vue's kebab) or `null` (open from a generic surface, user
// picks platform inside the dialog).
//
// Flow:
//   1. `showUploadRomDialog(platform | null)` opens the dialog and
//      fetches the supported-platforms list. v1 supports an id=-1
//      sentinel meaning "the fs_slug exists but no Platform record
//      has been created yet" — uploading auto-creates it via
//      `platformApi.uploadPlatform({ fsSlug })`.
//   2. User selects a platform (RSelect, searchable, with PlatformIcon
//      in selection + item slots) and adds files via the drop zone or
//      the native picker.
//   3. Upload streams through `romApi.uploadRoms` (already wired to
//      `storeUpload` — the v2 UploadProgressToast shows the bar). On
//      success, kick off a `socket.emit("scan")` for that platform so
//      newly-arrived files get matched.
import { RBtn, RChip, RIcon } from "@v2/lib";
import { useDropZone } from "@vueuse/core";
import type { Emitter } from "mitt";
import { computed, inject, nextTick, onBeforeUnmount, ref } from "vue";
import { useI18n } from "vue-i18n";
import platformApi from "@/services/api/platform";
import romApi from "@/services/api/rom";
import socket from "@/services/socket";
import storeHeartbeat from "@/stores/heartbeat";
import type { Platform } from "@/stores/platforms";
import storeScanning from "@/stores/scanning";
import storeUpload from "@/stores/upload";
import type { Events } from "@/types/emitter";
import { formatBytes } from "@/utils";
import PlatformSelect from "@/v2/components/shared/PlatformSelect.vue";
import { useSnackbar } from "@/v2/composables/useSnackbar";
import RDialog from "@/v2/lib/overlays/RDialog/RDialog.vue";

defineOptions({ inheritAttrs: false });

const { t } = useI18n();
const emitter = inject<Emitter<Events>>("emitter");
const snackbar = useSnackbar();
const heartbeatStore = storeHeartbeat();
const scanningStore = storeScanning();
const uploadStore = storeUpload();

const show = ref(false);
const files = ref<File[]>([]);
const supportedPlatforms = ref<Platform[]>([]);
const platformsLoading = ref(false);
const selectedPlatformId = ref<number | null>(null);
const uploading = ref(false);

const fileInputRef = ref<HTMLInputElement | null>(null);
const dropZoneRef = ref<HTMLElement | null>(null);

// ── Open / close lifecycle ──────────────────────────────────────
const openHandler = (preselect: Platform | null) => {
  show.value = true;
  selectedPlatformId.value = preselect?.id ?? null;
  files.value = [];
  loadPlatforms();
};
emitter?.on("showUploadRomDialog", openHandler);
onBeforeUnmount(() => emitter?.off("showUploadRomDialog", openHandler));

async function loadPlatforms() {
  platformsLoading.value = true;
  try {
    const { data } = await platformApi.getSupportedPlatforms();
    supportedPlatforms.value = data
      .slice()
      .sort((a, b) => a.name.localeCompare(b.name));
  } catch (err) {
    const e = err as {
      response?: { data?: { detail?: string } };
      message?: string;
    };
    snackbar.error(
      `Unable to load platforms: ${
        e?.response?.data?.detail || e?.message || "unknown error"
      }`,
      { icon: "mdi-close-circle" },
    );
  } finally {
    platformsLoading.value = false;
  }
}

const selectedPlatform = computed<Platform | null>(() => {
  if (selectedPlatformId.value === null) return null;
  return (
    supportedPlatforms.value.find((p) => p.id === selectedPlatformId.value) ??
    null
  );
});

// ── File handling ───────────────────────────────────────────────
function triggerPicker() {
  fileInputRef.value?.click();
}

function addFiles(picked: File[]) {
  if (!picked.length) return;
  // De-dupe by name — matches v1 behaviour.
  const seen = new Set(files.value.map((f) => f.name));
  const fresh = picked.filter((f) => !seen.has(f.name));
  if (fresh.length > 0) {
    files.value = [...files.value, ...fresh];
  }
}

function onPick(evt: Event) {
  const input = evt.target as HTMLInputElement;
  addFiles(input.files ? Array.from(input.files) : []);
  input.value = "";
}

function removeFile(name: string) {
  files.value = files.value.filter((f) => f.name !== name);
}

const { isOverDropZone } = useDropZone(dropZoneRef, {
  onDrop(picked: File[] | null) {
    if (picked) addFiles(picked);
  },
  multiple: true,
  preventDefaultForUnhandled: true,
});

// ── Upload ──────────────────────────────────────────────────────
async function upload() {
  const platform = selectedPlatform.value;
  if (!platform || files.value.length === 0 || uploading.value) return;
  uploading.value = true;

  let platformId = platform.id;

  try {
    // Sentinel id=-1: fs_slug exists but no Platform yet. Create one
    // before pushing ROMs into it — same approach as v1.
    if (platformId === -1) {
      const { data: created } = await platformApi.uploadPlatform({
        fsSlug: platform.fs_slug,
      });
      platformId = created.id;
      snackbar.success(`Platform ${platform.name} created`, {
        icon: "mdi-check-bold",
      });
    }

    const responses = await romApi.uploadRoms({
      platformId,
      filesToUpload: files.value,
    });

    const ok = responses.filter((r) => r.status === "fulfilled").length;
    const fail = responses.filter((r) => r.status === "rejected").length;

    if (ok === 0) {
      snackbar.warning("All files skipped, nothing uploaded.", {
        icon: "mdi-information-outline",
      });
    } else {
      if (fail === 0) uploadStore.reset();
      snackbar.success(
        fail === 0
          ? `${ok} files uploaded · starting scan`
          : `${ok} uploaded · ${fail} skipped/failed · starting scan`,
        { icon: "mdi-check-bold" },
      );

      // Give the backend a beat to finish writing before we ask it to
      // scan — v1 uses a 2s buffer for the same reason.
      scanningStore.setScanning(true);
      if (!socket.connected) socket.connect();
      setTimeout(() => {
        socket.emit("scan", {
          platforms: [platformId],
          type: "quick",
          apis: heartbeatStore.getEnabledMetadataOptions().map((s) => s.value),
        });
      }, 2000);
    }

    closeDialog();
  } catch (err) {
    const e = err as {
      response?: { data?: { detail?: string }; statusText?: string };
      message?: string;
    };
    snackbar.error(
      `Unable to upload roms: ${
        e?.response?.data?.detail ||
        e?.response?.statusText ||
        e?.message ||
        "unknown error"
      }`,
      { icon: "mdi-close-circle" },
    );
  } finally {
    uploading.value = false;
  }
}

function closeDialog() {
  if (uploading.value) return;
  show.value = false;
  // Defer the reset so the close animation doesn't briefly show an
  // empty dialog before the panel slides out.
  nextTick(() => {
    files.value = [];
    selectedPlatformId.value = null;
  });
}
</script>

<template>
  <RDialog
    v-model="show"
    icon="mdi-cloud-upload-outline"
    :width="640"
    @close="closeDialog"
  >
    <template #header>
      <span>{{ t("common.upload-roms", "Upload ROMs") }}</span>
    </template>

    <template #content>
      <div class="r-v2-upload-rom__body">
        <!-- Platform picker -->
        <PlatformSelect
          v-model="selectedPlatformId"
          :items="supportedPlatforms"
          :placeholder="t('common.select-platform', 'Select a platform')"
          density="comfortable"
          prefix-label="stacked"
          :icon-size="22"
          :search-placeholder="t('common.search', 'Search')"
          :disabled="platformsLoading"
        >
          <template #prefix-label>
            <RIcon icon="mdi-controller" size="14" />
            {{ t("common.platform", "Platform") }}
          </template>
        </PlatformSelect>

        <!-- Drop zone — empty state when no files, switches to a file
             list when populated. -->
        <div
          ref="dropZoneRef"
          class="r-v2-upload-rom__dropzone"
          :class="{
            'r-v2-upload-rom__dropzone--active': isOverDropZone,
            'r-v2-upload-rom__dropzone--filled': files.length > 0,
          }"
        >
          <div v-if="files.length === 0" class="r-v2-upload-rom__empty">
            <RIcon
              :icon="
                isOverDropZone ? 'mdi-cloud-upload' : 'mdi-cloud-upload-outline'
              "
              size="40"
              color="primary"
              :class="{ 'r-v2-upload-rom__icon--pulse': isOverDropZone }"
            />
            <h3 class="r-v2-upload-rom__empty-title">
              {{
                isOverDropZone
                  ? t("common.dropzone-drag-over", "Drop the files here")
                  : t("common.dropzone-title", "Drag and drop ROM files")
              }}
            </h3>
            <p class="r-v2-upload-rom__empty-hint">
              {{
                t(
                  "common.dropzone-description",
                  "or click below to pick files from your device",
                )
              }}
            </p>
            <RBtn
              variant="outlined"
              color="primary"
              prepend-icon="mdi-plus"
              @click="triggerPicker"
            >
              {{ t("common.add", "Add files") }}
            </RBtn>
          </div>

          <div v-else class="r-v2-upload-rom__filled">
            <header class="r-v2-upload-rom__filled-head">
              <span>
                {{ t("common.upload-files-selected", { count: files.length }) }}
              </span>
              <RBtn
                variant="text"
                size="small"
                prepend-icon="mdi-plus"
                @click="triggerPicker"
              >
                {{ t("common.add", "Add") }}
              </RBtn>
            </header>
            <ul class="r-v2-upload-rom__list">
              <li v-for="f in files" :key="f.name" class="r-v2-upload-rom__row">
                <RIcon icon="mdi-file-outline" size="14" />
                <span class="r-v2-upload-rom__row-name">{{ f.name }}</span>
                <RChip size="x-small" variant="translucent">
                  {{ formatBytes(f.size) }}
                </RChip>
                <RBtn
                  variant="text"
                  size="x-small"
                  icon="mdi-close"
                  color="danger"
                  :aria-label="t('common.remove', 'Remove')"
                  @click="removeFile(f.name)"
                />
              </li>
            </ul>
          </div>
        </div>

        <input
          ref="fileInputRef"
          type="file"
          multiple
          class="r-v2-upload-rom__input"
          :aria-label="t('common.upload-roms', 'Upload ROMs')"
          @change="onPick"
        />
      </div>
    </template>

    <template #footer>
      <RBtn variant="text" :disabled="uploading" @click="closeDialog">
        {{ t("common.cancel") }}
      </RBtn>
      <RBtn
        variant="flat"
        color="primary"
        prepend-icon="mdi-cloud-upload-outline"
        :disabled="files.length === 0 || !selectedPlatform"
        :loading="uploading"
        @click="upload"
      >
        {{ t("common.upload") }}
      </RBtn>
    </template>
  </RDialog>
</template>

<style scoped>
.r-v2-upload-rom__body {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 4px 4px 8px;
}

.r-v2-upload-rom__input {
  position: absolute;
  width: 0;
  height: 0;
  opacity: 0;
  pointer-events: none;
}

/* ── Drop zone ───────────────────────────────────────────────────
   Dashed primary border that brightens on hover-with-files and goes
   solid when the user actually drags over the zone. */
.r-v2-upload-rom__dropzone {
  position: relative;
  min-height: 240px;
  border: 2px dashed
    color-mix(in srgb, var(--r-color-brand-primary) 30%, transparent);
  border-radius: var(--r-radius-lg);
  background: var(--r-color-bg-elevated);
  transition:
    border-color var(--r-motion-fast) var(--r-motion-ease-out),
    background var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-v2-upload-rom__dropzone--active {
  border-color: var(--r-color-brand-primary);
  background: color-mix(in srgb, var(--r-color-brand-primary) 8%, transparent);
}
.r-v2-upload-rom__dropzone--filled {
  border-style: solid;
  border-color: var(--r-color-border-strong);
}

/* ── Empty state ─────────────────────────────────────────────── */
.r-v2-upload-rom__empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  min-height: 240px;
  padding: 28px 16px;
  text-align: center;
}
.r-v2-upload-rom__empty-title {
  margin: 6px 0 0;
  font-size: 16px;
  font-weight: var(--r-font-weight-semibold);
  color: var(--r-color-fg);
}
.r-v2-upload-rom__empty-hint {
  margin: 0;
  font-size: 13px;
  color: var(--r-color-fg-muted);
  max-width: 360px;
  line-height: 1.5;
}
.r-v2-upload-rom__icon--pulse {
  animation: r-v2-upload-rom-pulse 1.4s ease-in-out infinite;
}
@keyframes r-v2-upload-rom-pulse {
  50% {
    transform: scale(1.12);
    filter: drop-shadow(
      0 0 12px color-mix(in srgb, var(--r-color-brand-primary) 60%, transparent)
    );
  }
}

/* ── Filled state ────────────────────────────────────────────── */
.r-v2-upload-rom__filled {
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.r-v2-upload-rom__filled-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 13px;
  font-weight: var(--r-font-weight-semibold);
  color: var(--r-color-fg);
}

.r-v2-upload-rom__list {
  list-style: none;
  margin: 0;
  padding: 0;
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-md);
  background: var(--r-color-bg-elevated);
  overflow: hidden;
  max-height: 280px;
  overflow-y: auto;
}
.r-v2-upload-rom__row {
  display: grid;
  grid-template-columns: auto 1fr auto auto;
  gap: 10px;
  align-items: center;
  padding: 8px 12px;
  font-size: 13px;
  color: var(--r-color-fg);
  border-bottom: 1px solid var(--r-color-border);
}
.r-v2-upload-rom__row:last-child {
  border-bottom: 0;
}
.r-v2-upload-rom__row-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
