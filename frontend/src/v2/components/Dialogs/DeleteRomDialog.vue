<script setup lang="ts">
// DeleteRomDialog — single or multi-ROM delete flow. Each row has a
// "also remove file from disk" checkbox; a global "exclude on delete" flag
// adds deleted filenames to the scan exclusion list so they don't re-appear.
import { RBtn, RCheckbox, RDialog, RIcon } from "@v2/lib";
import type { Emitter } from "mitt";
import { computed, inject, onBeforeUnmount, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useRouter, useRoute } from "vue-router";
import { ROUTES } from "@/plugins/router";
import configApi from "@/services/api/config";
import romApi from "@/services/api/rom";
import storeConfig from "@/stores/config";
import storeRoms, { type SimpleRom } from "@/stores/roms";
import type { Events } from "@/types/emitter";
import { useSnackbar } from "@/v2/composables/useSnackbar";
import storeGalleryRoms from "@/v2/stores/galleryRoms";
import storeGallerySelection from "@/v2/stores/gallerySelection";

defineOptions({ inheritAttrs: false });

const { t } = useI18n();
const router = useRouter();
const route = useRoute();
const show = ref(false);
const romsStore = storeRoms();
const galleryRomsStore = storeGalleryRoms();
const gallerySelectionStore = storeGallerySelection();
const roms = ref<SimpleRom[]>([]);
const romsToDeleteFromFs = ref<number[]>([]);
const excludeOnDelete = ref(false);
const platformId = ref<number>(0);
const deleting = ref(false);
const emitter = inject<Emitter<Events>>("emitter");
const snackbar = useSnackbar();
const configStore = storeConfig();

const openHandler = (romsToDelete: SimpleRom[]) => {
  roms.value = romsToDelete;
  platformId.value = romsToDelete[0]?.platform_id ?? 0;
  show.value = true;
};
emitter?.on("showDeleteRomDialog", openHandler);
onBeforeUnmount(() => emitter?.off("showDeleteRomDialog", openHandler));

const fsCount = computed(() => romsToDeleteFromFs.value.length);
const allOnFs = computed(
  () =>
    roms.value.length > 0 &&
    romsToDeleteFromFs.value.length === roms.value.length,
);

function toggleAllFs() {
  if (allOnFs.value) {
    romsToDeleteFromFs.value = [];
  } else {
    romsToDeleteFromFs.value = roms.value.map((r) => r.id);
  }
}

function toggleRomOnFs(id: number) {
  const idx = romsToDeleteFromFs.value.indexOf(id);
  if (idx >= 0) {
    romsToDeleteFromFs.value.splice(idx, 1);
  } else {
    romsToDeleteFromFs.value.push(id);
  }
}

function coverFor(rom: SimpleRom): string | null {
  return rom.path_cover_small ?? rom.url_cover ?? null;
}

async function deleteRoms() {
  if (deleting.value) return;
  deleting.value = true;

  // Snapshot the dialog state up front: the dialog is a singleton, so a
  // fresh `showDeleteRomDialog` event could replace these refs while the
  // request is in flight. Acting on the snapshot keeps the response tied
  // to the ROMs it actually processed.
  const targetRoms = roms.value;
  const targetPlatformId = platformId.value;
  const deleteFromFs = romsToDeleteFromFs.value;
  const exclude = excludeOnDelete.value;

  try {
    const response = await romApi.deleteRoms({
      roms: targetRoms,
      deleteFromFs,
    });
    // The backend deletes per-ROM and can partially fail; only prune the
    // ROMs it actually removed so a failed subset stays visible and
    // selected for the user to retry.
    const failedIds = new Set(response.data.failed_ids);
    const deletedRoms = targetRoms.filter((rom) => !failedIds.has(rom.id));
    snackbar.success(
      deleteFromFs.length > 0
        ? t("rom.deleted-from-filesystem", {
            count: response.data.successful_items,
          })
        : t("rom.deleted-from-database", {
            count: response.data.successful_items,
          }),
      { icon: "mdi-check-bold" },
    );
    if (exclude) {
      for (const rom of deletedRoms) {
        const type = rom.has_simple_single_file
          ? "EXCLUDED_SINGLE_FILES"
          : "EXCLUDED_MULTI_FILES";
        configApi.addExclusion({
          exclusionValue: rom.fs_name,
          exclusionType: type,
        });
        configStore.addExclusion(type, rom.fs_name);
      }
    }
    romsStore.resetSelection();
    // Drop the deleted ROMs from the v2 gallery selection too — otherwise
    // the SelectionBar stays open pointing at rows that no longer exist,
    // and re-running an action 404s. removeIds only touches the deleted
    // subset, so a partial (or failed) delete keeps the rest selected.
    gallerySelectionStore.removeIds(deletedRoms.map((rom) => rom.id));
    romsStore.remove(deletedRoms);
    galleryRomsStore.remove(deletedRoms);
    romsStore.setRecentRoms(
      romsStore.recentRoms.filter(
        (r) => !deletedRoms.some((rom) => rom.id === r.id),
      ),
    );
    romsStore.setContinuePlayingRoms(
      romsStore.continuePlayingRoms.filter(
        (r) => !deletedRoms.some((rom) => rom.id === r.id),
      ),
    );
    emitter?.emit("refreshDrawer", null);
    closeDialog();
    // Only leave the single-ROM route when that ROM was actually deleted.
    if (route.name === "rom" && deletedRoms.length > 0) {
      router.push({
        name: ROUTES.PLATFORM,
        params: { platform: targetPlatformId },
      });
    }
  } catch (error: unknown) {
    console.error(error);
    const axiosErr = error as { response?: { data?: { detail?: string } } };
    snackbar.error(
      axiosErr.response?.data?.detail ?? t("rom.delete-roms-failed"),
      {
        icon: "mdi-close-circle",
      },
    );
  } finally {
    deleting.value = false;
  }
}

function closeDialog() {
  romsToDeleteFromFs.value = [];
  roms.value = [];
  excludeOnDelete.value = false;
  show.value = false;
}
</script>

<template>
  <RDialog
    v-model="show"
    icon="mdi-delete-outline"
    scroll-content
    width="560"
    @close="closeDialog"
  >
    <template #header>
      <span>{{ t("rom.removing-title", roms.length) }}</span>
    </template>
    <template #toolbar>
      <div class="r-v2-del-rom__toolbar">
        <span class="r-v2-del-rom__hint">
          {{ t("rom.delete-select-instruction") }}
        </span>
        <button
          type="button"
          class="r-v2-del-rom__toggle-all"
          :aria-pressed="allOnFs"
          @click="toggleAllFs"
        >
          <RIcon
            :icon="
              allOnFs
                ? 'mdi-checkbox-multiple-marked'
                : 'mdi-checkbox-multiple-blank-outline'
            "
            size="14"
          />
          {{ allOnFs ? t("rom.unselect-all") : t("rom.select-all-disk") }}
        </button>
      </div>
    </template>
    <template #content>
      <ul class="r-v2-del-rom__list">
        <li
          v-for="rom in roms"
          :key="rom.id"
          class="r-v2-del-rom__row"
          :class="{
            'r-v2-del-rom__row--fs': romsToDeleteFromFs.includes(rom.id),
          }"
        >
          <div class="r-v2-del-rom__cover">
            <img
              v-if="coverFor(rom)"
              :src="coverFor(rom)!"
              :alt="rom.name ?? ''"
            />
            <div v-else class="r-v2-del-rom__cover-placeholder">
              <RIcon icon="mdi-disc" size="18" />
            </div>
          </div>
          <div class="r-v2-del-rom__meta">
            <p class="r-v2-del-rom__name" :title="rom.name ?? undefined">
              {{ rom.name || rom.fs_name }}
            </p>
            <p class="r-v2-del-rom__file" :title="rom.fs_name">
              {{ rom.fs_name }}
            </p>
          </div>
          <button
            type="button"
            class="r-v2-del-rom__fs-toggle"
            :aria-pressed="romsToDeleteFromFs.includes(rom.id)"
            :aria-label="t('rom.delete-from-disk-aria', { name: rom.fs_name })"
            :class="{
              'r-v2-del-rom__fs-toggle--on': romsToDeleteFromFs.includes(
                rom.id,
              ),
            }"
            @click="toggleRomOnFs(rom.id)"
          >
            <RIcon icon="mdi-harddisk-remove" size="14" />
            {{ t("rom.delete-file") }}
          </button>
        </li>
      </ul>
    </template>
    <template #append>
      <div class="r-v2-del-rom__append">
        <RCheckbox
          v-model="excludeOnDelete"
          hide-details
          :label="t('common.exclude-on-delete')"
        />
        <p v-if="fsCount > 0" class="r-v2-del-rom__warn">
          <RIcon icon="mdi-alert" size="14" color="var(--r-color-danger-fg)" />
          <span>
            <strong>{{ t("common.warning") }}:</strong>
            {{ t("rom.delete-filesystem-warning", fsCount) }}
          </span>
        </p>
      </div>
    </template>
    <template #footer>
      <RBtn variant="text" :disabled="deleting" @click="closeDialog">
        {{ t("common.cancel") }}
      </RBtn>
      <div style="flex: 1" />
      <RBtn
        variant="translucent"
        color="error"
        prepend-icon="mdi-delete"
        :loading="deleting"
        :disabled="deleting || roms.length === 0"
        @click="deleteRoms"
      >
        {{ t("common.confirm") }}
      </RBtn>
    </template>
  </RDialog>
</template>

<style scoped>
.r-v2-del-rom__toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  font-size: 12px;
  color: var(--r-color-fg-muted);
}
.r-v2-del-rom__hint {
  flex: 1;
}

.r-v2-del-rom__toggle-all {
  appearance: none;
  background: var(--r-color-bg-elevated);
  border: 1px solid var(--r-color-border);
  color: var(--r-color-fg-secondary);
  padding: 4px 10px;
  border-radius: var(--r-radius-pill);
  font-size: 11px;
  font-weight: var(--r-font-weight-medium);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-family: inherit;
}
.r-v2-del-rom__toggle-all:hover {
  background: var(--r-color-surface);
}

.r-v2-del-rom__list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 360px;
  overflow-y: auto;
}

.r-v2-del-rom__row {
  display: grid;
  grid-template-columns: 36px 1fr auto;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  background: var(--r-color-bg-elevated);
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-md);
  transition: border-color var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-v2-del-rom__row--fs {
  border-color: color-mix(
    in srgb,
    var(--r-color-status-base-danger) 35%,
    transparent
  );
  background: color-mix(
    in srgb,
    var(--r-color-status-base-danger) 6%,
    transparent
  );
}

.r-v2-del-rom__cover {
  width: 36px;
  aspect-ratio: 3 / 4;
  border-radius: var(--r-radius-sm);
  overflow: hidden;
  background: var(--r-color-cover-placeholder);
  display: grid;
  place-items: center;
}
.r-v2-del-rom__cover img {
  width: 100%;
  height: 100%;
  /* Show the whole cover at its natural aspect (no crop); the slot stays a
     uniform width so the delete list's rows keep their alignment. */
  object-fit: contain;
  display: block;
}
.r-v2-del-rom__cover-placeholder {
  color: var(--r-color-fg-faint);
}

.r-v2-del-rom__meta {
  min-width: 0;
}
.r-v2-del-rom__name {
  margin: 0;
  font-size: 13px;
  font-weight: var(--r-font-weight-medium);
  color: var(--r-color-fg);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.r-v2-del-rom__file {
  margin: 2px 0 0;
  font-size: 11px;
  font-family: var(--r-font-family-mono, monospace);
  color: var(--r-color-fg-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.r-v2-del-rom__fs-toggle {
  appearance: none;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  background: var(--r-color-bg-elevated);
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-pill);
  font-size: 11px;
  color: var(--r-color-fg-secondary);
  font-weight: var(--r-font-weight-medium);
  font-family: inherit;
  cursor: pointer;
  transition:
    background var(--r-motion-fast) var(--r-motion-ease-out),
    color var(--r-motion-fast) var(--r-motion-ease-out),
    border-color var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-v2-del-rom__fs-toggle:hover {
  background: var(--r-color-surface);
  color: var(--r-color-fg);
}
.r-v2-del-rom__fs-toggle--on,
.r-v2-del-rom__fs-toggle--on:hover {
  background: color-mix(
    in srgb,
    var(--r-color-status-base-danger) 18%,
    transparent
  );
  border-color: color-mix(
    in srgb,
    var(--r-color-status-base-danger) 40%,
    transparent
  );
  color: var(--r-color-danger-fg);
}

.r-v2-del-rom__append {
  padding: 10px 14px 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.r-v2-del-rom__warn {
  display: flex;
  gap: 8px;
  padding: 8px 10px;
  margin: 0;
  background: color-mix(
    in srgb,
    var(--r-color-status-base-danger) 10%,
    transparent
  );
  border: 1px solid
    color-mix(in srgb, var(--r-color-status-base-danger) 25%, transparent);
  border-radius: var(--r-radius-md);
  color: var(--r-color-fg);
  font-size: 12px;
  line-height: 1.4;
}
.r-v2-del-rom__warn strong {
  color: var(--r-color-danger-fg);
}
</style>
