<script setup lang="ts">
// DeleteRomDialog: single or multi-ROM delete flow. Each row has a
// "also remove file from disk" checkbox; a global "exclude on delete" flag
// adds deleted filenames to the scan exclusion list so they don't re-appear.
// Rows are virtualised so a whole-library selection doesn't mount every cover.
import { RBtn, RCheckbox, RDialog, RIcon, RVirtualScroller } from "@v2/lib";
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
import { useRomSync } from "@/v2/composables/useRomSync";
import { romIdFromRoute } from "@/v2/composables/useRouteRom";
import { useSnackbar } from "@/v2/composables/useSnackbar";
import { settleWithLimit } from "@/v2/utils/settleWithLimit";

defineOptions({ inheritAttrs: false });

// A 66px row plus the 6px gap below it; `.r-v2-del-rom__row` pins the row.
const ROW_HEIGHT_PX = 72;
const LIST_MAX_HEIGHT_PX = 360;

const { t } = useI18n();
const router = useRouter();
const route = useRoute();
const show = ref(false);
const romsStore = storeRoms();
const { removeCachedRoms } = useRomSync();
const roms = ref<SimpleRom[]>([]);
const romsToDeleteFromFs = ref<number[]>([]);
const excludeOnDelete = ref(false);
const platformId = ref<number>(0);
const deleting = ref(false);
const emitter = inject<Emitter<Events>>("emitter");
const snackbar = useSnackbar();
const configStore = storeConfig();
const listHeight = computed(() =>
  Math.min(roms.value.length * ROW_HEIGHT_PX, LIST_MAX_HEIGHT_PX),
);
const fsIds = computed(() => new Set(romsToDeleteFromFs.value));
const rowHeight = () => ROW_HEIGHT_PX;
const rowKey = (rom: unknown) => (rom as SimpleRom).id;

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
      const exclusionType = (rom: SimpleRom) =>
        rom.has_simple_single_file
          ? "EXCLUDED_SINGLE_FILES"
          : "EXCLUDED_MULTI_FILES";
      // One at a time: each call rewrites the config file server-side.
      const results = await settleWithLimit(deletedRoms, 1, (rom) =>
        configApi.addExclusion({
          exclusionValue: rom.fs_name,
          exclusionType: exclusionType(rom),
        }),
      );
      let failed = 0;
      results.forEach((result, i) => {
        const rom = deletedRoms[i];
        if (result.status === "fulfilled") {
          configStore.addExclusion(exclusionType(rom), rom.fs_name);
        } else {
          failed++;
        }
      });
      if (failed > 0) {
        snackbar.error(t("rom.exclude-failed", { n: failed }), {
          icon: "mdi-close-circle",
        });
      }
    }
    romsStore.resetSelection();
    removeCachedRoms(deletedRoms);
    // Deletion is permanent, so unlike the other `removeCachedRoms` callers
    // this one also takes the ROMs out of Home's rows.
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
      // The delete already succeeded, so a failed redirect is only logged.
      await router
        .push({ name: ROUTES.PLATFORM, params: { platform: targetPlatformId } })
        .catch((error: unknown) => console.error(error));
    }
    // A page still on a deleted game (the redirect failed) keeps its record.
    const shownId = romIdFromRoute(route);
    romsStore.forgetDetailedRoms(
      deletedRoms.map((rom) => rom.id).filter((id) => id !== shownId),
    );
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
    cancelable
    :cancel-disabled="deleting"
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
      <RVirtualScroller
        :items="roms"
        :get-item-height="rowHeight"
        :get-item-key="rowKey"
        :height="listHeight"
        role="list"
      >
        <template #default="{ item }">
          <div
            v-for="rom in [item as SimpleRom]"
            :key="rom.id"
            role="listitem"
            class="r-v2-del-rom__row"
            :class="{ 'r-v2-del-rom__row--fs': fsIds.has(rom.id) }"
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
              :aria-pressed="fsIds.has(rom.id)"
              :aria-label="
                t('rom.delete-from-disk-aria', { name: rom.fs_name })
              "
              :class="{ 'r-v2-del-rom__fs-toggle--on': fsIds.has(rom.id) }"
              @click="toggleRomOnFs(rom.id)"
            >
              <RIcon icon="mdi-harddisk-remove" size="14" />
              {{ t("rom.delete-file") }}
            </button>
          </div>
        </template>
      </RVirtualScroller>
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

.r-v2-del-rom__row {
  box-sizing: border-box;
  height: 66px;
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
  padding: 10px 14px 12px;
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
