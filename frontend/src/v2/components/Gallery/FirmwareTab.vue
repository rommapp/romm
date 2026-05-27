<script setup lang="ts">
// FirmwareTab — platform-scoped firmware manager rendered as the
// `Firmware` tab inside Platform.vue. Lists every firmware file
// associated with the platform and lets admins upload, download, or
// delete files. Same content surface as the previous
// `FirmwareDrawer`, but now lives inline in the platform view.
//
// Mutation paths (all routed through `firmwareApi`):
//   • Upload  → `UploadFirmwareDialog` (file picker → multipart POST)
//   • Delete  → `DeleteFirmwareDialog` (bulk confirm + per-item
//               "also delete from filesystem" checkboxes)
//   • Download → direct `<a download>` (no API call needed)
//
// The list state and selection set live here; the dialogs are pure
// presentational forms driven by props/emits. On success, the parent
// `galleryRoms.currentPlatform.firmware` array is refreshed inline so
// neither the gallery rebuild nor a full platform refetch is required.
import { RBtn, RChip, RCheckbox, REmptyState, RIcon, RTooltip } from "@v2/lib";
import { computed, ref } from "vue";
import { useI18n } from "vue-i18n";
import type { FirmwareSchema } from "@/__generated__";
import firmwareApi from "@/services/api/firmware";
import type { Platform } from "@/stores/platforms";
import storePlatforms from "@/stores/platforms";
import { formatBytes } from "@/utils";
import DeleteFirmwareDialog from "@/v2/components/Gallery/DeleteFirmwareDialog.vue";
import UploadFirmwareDialog from "@/v2/components/Gallery/UploadFirmwareDialog.vue";
import { useCan } from "@/v2/composables/useCan";
import { useSnackbar } from "@/v2/composables/useSnackbar";
import storeGalleryRoms from "@/v2/stores/galleryRoms";

defineOptions({ inheritAttrs: false });

const props = defineProps<{
  platform: Platform;
}>();

const { t } = useI18n();
const snackbar = useSnackbar();
const platformsStore = storePlatforms();
const galleryRoms = storeGalleryRoms();
const canWrite = useCan("platform.edit");

const selectedIds = ref<Set<number>>(new Set());

const firmwareList = computed<FirmwareSchema[]>(
  () => props.platform.firmware ?? [],
);

const selectedFirmware = computed<FirmwareSchema[]>(() =>
  firmwareList.value.filter((f) => selectedIds.value.has(f.id)),
);

const allSelected = computed(
  () =>
    firmwareList.value.length > 0 &&
    selectedIds.value.size === firmwareList.value.length,
);
const someSelected = computed(
  () =>
    selectedIds.value.size > 0 &&
    selectedIds.value.size < firmwareList.value.length,
);

function toggleAll() {
  if (allSelected.value) {
    selectedIds.value = new Set();
  } else {
    selectedIds.value = new Set(firmwareList.value.map((f) => f.id));
  }
}

function toggleOne(id: number) {
  const next = new Set(selectedIds.value);
  if (next.has(id)) next.delete(id);
  else next.add(id);
  selectedIds.value = next;
}

const uploadOpen = ref(false);
function openUpload() {
  uploadOpen.value = true;
}
function onUploaded(updated: FirmwareSchema[]) {
  syncFirmware(updated);
}

function downloadOne(f: FirmwareSchema) {
  const a = document.createElement("a");
  a.href = `/api/firmware/${f.id}/content/${f.file_name}`;
  a.download = f.file_name;
  a.click();
}
function downloadSelected() {
  for (const f of selectedFirmware.value) downloadOne(f);
}

const deleteOpen = ref(false);
const pendingDelete = ref<FirmwareSchema[]>([]);

function openDelete(target: FirmwareSchema[]) {
  pendingDelete.value = target;
  deleteOpen.value = true;
}
function onDeleted(deletedIds: number[]) {
  const remaining = firmwareList.value.filter(
    (f) => !deletedIds.includes(f.id),
  );
  syncFirmware(remaining);
  const next = new Set(selectedIds.value);
  for (const id of deletedIds) next.delete(id);
  selectedIds.value = next;
}

// `firmware_count` is a readonly derived field on PlatformSchema —
// patched locally so the InfoPanel stat reacts instantly; a future
// refetch reconciles.
function syncFirmware(next: FirmwareSchema[]) {
  const updated: Platform = {
    ...props.platform,
    firmware: next,
    firmware_count: next.length,
  };
  platformsStore.update(updated);
  if (galleryRoms.currentPlatform?.id === updated.id) {
    galleryRoms.setCurrentPlatform(updated);
  }
}

function onDeleteError(err: unknown) {
  const e = err as {
    response?: { data?: { detail?: string } };
    message?: string;
  };
  snackbar.error(
    `Failed to delete firmware: ${
      e?.response?.data?.detail || e?.message || "unknown error"
    }`,
    { icon: "mdi-close-circle" },
  );
}

async function performDelete(
  firmware: FirmwareSchema[],
  deleteFromFs: number[],
): Promise<void> {
  try {
    await firmwareApi.deleteFirmware({ firmware, deleteFromFs });
    onDeleted(firmware.map((f) => f.id));
    snackbar.success(
      t("platform.firmware-deleted-successfully", { count: firmware.length }),
      { icon: "mdi-check-circle" },
    );
  } catch (err) {
    onDeleteError(err);
    throw err;
  }
}
</script>

<template>
  <div class="r-v2-fw">
    <header
      v-if="firmwareList.length > 0"
      class="r-v2-fw__toolbar"
      :class="{ 'r-v2-fw__toolbar--active': selectedIds.size > 0 }"
    >
      <RCheckbox
        :model-value="allSelected"
        :indeterminate="someSelected"
        hide-details
        :label="
          selectedIds.size > 0
            ? t('gallery.firmware-selected-count', { count: selectedIds.size })
            : t('gallery.firmware-files-count', { count: firmwareList.length })
        "
        @update:model-value="toggleAll"
      />
      <div class="r-v2-fw__toolbar-actions">
        <RBtn
          v-if="canWrite"
          variant="text"
          size="small"
          prepend-icon="mdi-cloud-upload-outline"
          @click="openUpload"
        >
          {{ t("common.upload") }}
        </RBtn>
        <RBtn
          variant="text"
          size="small"
          prepend-icon="mdi-download"
          :disabled="selectedIds.size === 0"
          @click="downloadSelected"
        >
          {{ t("common.download") }}
        </RBtn>
        <RBtn
          v-if="canWrite"
          variant="text"
          size="small"
          color="danger"
          prepend-icon="mdi-delete-outline"
          :disabled="selectedIds.size === 0"
          @click="openDelete(selectedFirmware)"
        >
          {{ t("common.delete") }}
        </RBtn>
      </div>
    </header>

    <ul v-if="firmwareList.length > 0" class="r-v2-fw__list">
      <li
        v-for="f in firmwareList"
        :key="f.id"
        class="r-v2-fw__row"
        :class="{
          'r-v2-fw__row--selected': selectedIds.has(f.id),
          'r-v2-fw__row--missing': f.missing_from_fs,
        }"
      >
        <RCheckbox
          :model-value="selectedIds.has(f.id)"
          hide-details
          class="r-v2-fw__row-check"
          @update:model-value="toggleOne(f.id)"
        />
        <div class="r-v2-fw__row-body">
          <div class="r-v2-fw__row-name-line">
            <RTooltip
              v-if="f.missing_from_fs"
              :text="
                t(
                  'platform.firmware-missing-from-fs',
                  'Missing from filesystem',
                )
              "
            >
              <template #activator="{ props: act }">
                <RIcon
                  v-bind="act"
                  icon="mdi-file-question-outline"
                  size="14"
                  color="var(--r-color-danger-fg)"
                />
              </template>
            </RTooltip>
            <span class="r-v2-fw__row-name">{{ f.file_name }}</span>
          </div>
          <div class="r-v2-fw__row-chips">
            <RChip size="x-small" variant="translucent">
              {{ formatBytes(f.file_size_bytes) }}
            </RChip>
            <RChip
              size="x-small"
              variant="translucent"
              color="info"
              class="r-v2-fw__row-hash"
              :title="`MD5: ${f.md5_hash}`"
            >
              {{ f.md5_hash }}
            </RChip>
            <RChip
              v-if="f.is_verified"
              size="x-small"
              color="success"
              variant="translucent"
              prepend-icon="mdi-check-circle"
              :title="
                t(
                  'platform.firmware-verified-tooltip',
                  'Passed size, SHA1 and MD5 checksum checks',
                )
              "
            >
              {{ t("platform.firmware-verified", "Verified") }}
            </RChip>
          </div>
        </div>
        <div class="r-v2-fw__row-actions">
          <RBtn
            variant="text"
            size="small"
            icon="mdi-download"
            :aria-label="t('common.download')"
            :title="t('common.download')"
            @click="downloadOne(f)"
          />
          <RBtn
            v-if="canWrite"
            variant="text"
            size="small"
            icon="mdi-delete-outline"
            color="danger"
            :aria-label="t('common.delete')"
            :title="t('common.delete')"
            @click="openDelete([f])"
          />
        </div>
      </li>
    </ul>

    <REmptyState
      v-else
      variant="boxed"
      icon="mdi-memory"
      :message="
        t('platform.no-firmware-found', 'No firmware found for this platform.')
      "
    >
      <template v-if="canWrite" #actions>
        <RBtn
          variant="flat"
          color="primary"
          prepend-icon="mdi-cloud-upload-outline"
          @click="openUpload"
        >
          {{ t("platform.upload-firmware", "Upload firmware") }}
        </RBtn>
      </template>
    </REmptyState>
  </div>

  <UploadFirmwareDialog
    v-model="uploadOpen"
    :platform="platform"
    @uploaded="onUploaded"
  />

  <DeleteFirmwareDialog
    v-model="deleteOpen"
    :firmware="pendingDelete"
    :on-confirm="performDelete"
  />
</template>

<style scoped>
.r-v2-fw {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

/* ── Toolbar ───────────────────────────────────────────────────── */
.r-v2-fw__toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 8px 10px;
  background: var(--r-color-bg-elevated);
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-md);
  transition:
    background var(--r-motion-fast) var(--r-motion-ease-out),
    border-color var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-v2-fw__toolbar--active {
  background: color-mix(in srgb, var(--r-color-brand-primary) 10%, transparent);
  border-color: color-mix(
    in srgb,
    var(--r-color-brand-primary) 40%,
    transparent
  );
}

.r-v2-fw__toolbar-actions {
  display: inline-flex;
  align-items: center;
  gap: 2px;
}

/* ── List ──────────────────────────────────────────────────────── */
.r-v2-fw__list {
  list-style: none;
  margin: 0;
  padding: 0;
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-md);
  overflow: hidden;
  background: var(--r-color-bg-elevated);
}
.r-v2-fw__row {
  display: grid;
  grid-template-columns: auto 1fr auto;
  gap: 10px;
  align-items: center;
  padding: 10px 12px;
  border-bottom: 1px solid var(--r-color-border);
  transition: background var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-v2-fw__row:last-child {
  border-bottom: 0;
}
.r-v2-fw__row:hover {
  background: var(--r-color-surface-hover);
}
.r-v2-fw__row--selected {
  background: color-mix(in srgb, var(--r-color-brand-primary) 8%, transparent);
}
.r-v2-fw__row--missing .r-v2-fw__row-name {
  color: var(--r-color-fg-muted);
  text-decoration: line-through;
}

.r-v2-fw__row-check {
  align-self: center;
}

.r-v2-fw__row-body {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.r-v2-fw__row-name-line {
  display: flex;
  align-items: center;
  gap: 6px;
}
.r-v2-fw__row-name {
  font-size: 13px;
  font-weight: var(--r-font-weight-medium);
  color: var(--r-color-fg);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.r-v2-fw__row-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
.r-v2-fw__row-hash {
  max-width: 220px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: var(--r-font-family-mono, monospace);
}

.r-v2-fw__row-actions {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  flex-shrink: 0;
}
</style>
