<script setup lang="ts">
// Upload — Library Tools view that posts ROM files to a chosen
// platform. Replaces the old emitter-driven `UploadRomDialog`; entry
// points (UserMenu, Platform.vue kebab) now navigate here with the
// `?platform=<id>` query param when they have a preselection.
//
// Flow mirrors the dialog version that came before it:
//   1. On mount, fetch the supported-platforms catalogue (v1's
//      sentinel id=-1 "the fs_slug exists but no Platform record yet"
//      is preserved — uploading auto-creates the platform via
//      `platformApi.uploadPlatform({ fsSlug })`).
//   2. User picks a platform (PlatformSelect handles search +
//      iconography) and adds files via drop zone or native picker.
//   3. Upload streams through `romApi.uploadRoms` (already wired to
//      `storeUpload` — the v2 UploadProgressToast shows the bar). On
//      success we stay on the view (this is a tool — users will often
//      upload more) but clear the file list. A scan is kicked off
//      automatically so newly arrived files get matched.
import { RBtn, RChip, RDropzone, RIcon } from "@v2/lib";
import { computed, onMounted, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute } from "vue-router";
import platformApi from "@/services/api/platform";
import romApi from "@/services/api/rom";
import socket from "@/services/socket";
import storeHeartbeat from "@/stores/heartbeat";
import type { Platform } from "@/stores/platforms";
import storeScanning from "@/stores/scanning";
import storeUpload from "@/stores/upload";
import { formatBytes } from "@/utils";
import PlatformSelect from "@/v2/components/shared/PlatformSelect.vue";
import { useSnackbar } from "@/v2/composables/useSnackbar";

const { t } = useI18n();
const route = useRoute();
const snackbar = useSnackbar();
const heartbeatStore = storeHeartbeat();
const scanningStore = storeScanning();
const uploadStore = storeUpload();

const files = ref<File[]>([]);
const supportedPlatforms = ref<Platform[]>([]);
const platformsLoading = ref(false);
const selectedPlatformId = ref<number | null>(null);
const uploading = ref(false);

const uploadDz = ref<InstanceType<typeof RDropzone> | null>(null);

// ── Platform list bootstrap ────────────────────────────────────
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
      t("common.unable-to-load-platforms", {
        error:
          e?.response?.data?.detail || e?.message || t("common.unknown-error"),
      }),
      { icon: "mdi-close-circle" },
    );
  } finally {
    platformsLoading.value = false;
  }
}

// Honour `?platform=<id>` on first paint and whenever the query
// changes (in-app navigation between Platforms keeps the view but
// swaps preselection). Falls back to `null` so the picker reads as
// empty when no query is present.
function applyPreselectFromQuery() {
  const raw = route.query.platform;
  const value = Array.isArray(raw) ? raw[0] : raw;
  if (!value) {
    return;
  }
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return;
  selectedPlatformId.value = parsed;
}

onMounted(() => {
  loadPlatforms();
  applyPreselectFromQuery();
});

watch(() => route.query.platform, applyPreselectFromQuery);

const selectedPlatform = computed<Platform | null>(() => {
  if (selectedPlatformId.value === null) return null;
  return (
    supportedPlatforms.value.find((p) => p.id === selectedPlatformId.value) ??
    null
  );
});

// ── File handling ───────────────────────────────────────────────
function addFiles(picked: File[]) {
  if (!picked.length) return;
  // De-dupe by name — matches v1 behaviour.
  const seen = new Set(files.value.map((f) => f.name));
  const fresh = picked.filter((f) => !seen.has(f.name));
  if (fresh.length > 0) {
    files.value = [...files.value, ...fresh];
  }
}

function removeFile(name: string) {
  files.value = files.value.filter((f) => f.name !== name);
}

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
      snackbar.success(t("common.platform-created", { name: platform.name }), {
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
      snackbar.warning(t("common.all-files-skipped"), {
        icon: "mdi-information-outline",
      });
    } else {
      if (fail === 0) uploadStore.reset();
      snackbar.success(
        fail === 0
          ? t("common.uploaded-and-scanning", { ok })
          : t("common.uploaded-with-failed", { ok, fail }),
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

      // Clear the list so the next batch starts fresh; keep the
      // platform selected so a user can chain uploads.
      files.value = [];
    }
  } catch (err) {
    const e = err as {
      response?: { data?: { detail?: string }; statusText?: string };
      message?: string;
    };
    snackbar.error(
      t("common.unable-to-upload-roms", {
        error:
          e?.response?.data?.detail ||
          e?.response?.statusText ||
          e?.message ||
          t("common.unknown-error"),
      }),
      { icon: "mdi-close-circle" },
    );
  } finally {
    uploading.value = false;
  }
}
</script>

<template>
  <div class="r-v2-upload r-v2-section-stack">
    <!-- Platform picker -->
    <PlatformSelect
      v-model="selectedPlatformId"
      :items="supportedPlatforms"
      :placeholder="t('common.select-platform')"
      density="comfortable"
      prefix-label="stacked"
      :icon-size="22"
      :search-placeholder="t('common.search')"
      :disabled="platformsLoading"
    >
      <template #prefix-label>
        <RIcon icon="mdi-controller" size="14" />
        {{ t("common.platform") }}
      </template>
    </PlatformSelect>

    <!-- Drop zone — CTA when empty, file list (with drag overlay) when
           populated. -->
    <RDropzone
      v-if="files.length === 0"
      :title="t('common.dropzone-title')"
      :hint="t('common.dropzone-description')"
      :active-title="t('common.dropzone-drag-over')"
      :input-label="t('common.upload-roms')"
      multiple
      @files="addFiles"
    />
    <RDropzone
      v-else
      ref="uploadDz"
      overlay
      :release-label="t('common.dropzone-drag-over')"
      :input-label="t('common.upload-roms')"
      multiple
      @files="addFiles"
    >
      <div class="r-v2-upload__filled">
        <header class="r-v2-upload__filled-head">
          <span>
            {{ t("common.upload-files-selected", { count: files.length }) }}
          </span>
          <RBtn
            variant="text"
            size="small"
            prepend-icon="mdi-plus"
            @click="uploadDz?.open()"
          >
            {{ t("common.add") }}
          </RBtn>
        </header>
        <ul class="r-v2-upload__list">
          <li v-for="f in files" :key="f.name" class="r-v2-upload__row">
            <RIcon icon="mdi-file-outline" size="14" />
            <span class="r-v2-upload__row-name">{{ f.name }}</span>
            <RChip size="x-small" variant="translucent">
              {{ formatBytes(f.size) }}
            </RChip>
            <RBtn
              variant="text"
              size="x-small"
              icon="mdi-close"
              color="danger"
              :aria-label="t('common.remove')"
              @click="removeFile(f.name)"
            />
          </li>
        </ul>
      </div>
    </RDropzone>

    <!-- Footer — primary CTA. No Cancel: this is a view, not a
           dialog, the user just navigates away if they change their
           mind. -->
    <div class="r-v2-upload__footer">
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
    </div>
  </div>
</template>

<style scoped>
/* ── Filled state ────────────────────────────────────────────── */
.r-v2-upload__filled {
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.r-v2-upload__filled-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 13px;
  font-weight: var(--r-font-weight-semibold);
  color: var(--r-color-fg);
}

.r-v2-upload__list {
  list-style: none;
  margin: 0;
  padding: 0;
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-md);
  background: var(--r-color-bg-elevated);
  overflow: hidden;
  max-height: 320px;
  overflow-y: auto;
}
.r-v2-upload__row {
  display: grid;
  grid-template-columns: auto 1fr auto auto;
  gap: 10px;
  align-items: center;
  padding: 8px 12px;
  font-size: 13px;
  color: var(--r-color-fg);
  border-bottom: 1px solid var(--r-color-border);
}
.r-v2-upload__row:last-child {
  border-bottom: 0;
}
.r-v2-upload__row-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.r-v2-upload__footer {
  display: flex;
  justify-content: flex-end;
}
</style>
