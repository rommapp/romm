<script setup lang="ts">
// SaveDataTab — Saves + States, each its own subtab with badge counts
// and per-tab Upload affordance. Layout mirrors ScreenshotsSubtab: a
// vertical subtab list on the left (navigation only — no inline action
// panel), and per-section headers in the content column with the
// Upload button on the right when the section already has items. Empty
// sections promote the dropzone CTA (the dropzone owns the upload
// affordance there).
//
// Each list is split into a "Mine" section (own saves/states, with a
// per-item public/private toggle + delete) and a read-only "Community"
// section (other users' public saves/states, with an author chip and
// download only). Mirrors ScreenshotsSubtab's My / Community model.
//
// URL-persistent subtab selection via `?subtab=` so deep-linking
// into a specific list works and stale state doesn't leak when the
// user navigates to a sibling tab.
import { RBtn, RDropzone, RIcon } from "@v2/lib";
import axios from "axios";
import { storeToRefs } from "pinia";
import { computed, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute, useRouter } from "vue-router";
import type {
  DetailedRomSchema,
  SaveSchema,
  StateSchema,
  UserSaveSchema,
  UserStateSchema,
} from "@/__generated__";
import romApi from "@/services/api/rom";
import saveApi from "@/services/api/save";
import stateApi from "@/services/api/state";
import storeAuth from "@/stores/auth";
import storeRoms from "@/stores/roms";
import AssetList from "@/v2/components/shared/AssetList.vue";
import AssetStrip from "@/v2/components/shared/AssetStrip.vue";
import { useConfirm } from "@/v2/composables/useConfirm";
import { useSnackbar } from "@/v2/composables/useSnackbar";

// Slot payload from AssetList/AssetStrip is the full save|state union; these
// narrow it back to the concrete schema the section's handlers expect.
type AssetSlot = SaveSchema | StateSchema | UserSaveSchema | UserStateSchema;
const asSave = (a: AssetSlot) => a as SaveSchema;
const asState = (a: AssetSlot) => a as StateSchema;

defineOptions({ inheritAttrs: false });

const props = defineProps<{ rom: DetailedRomSchema }>();
const { t } = useI18n();

// ---------- Subtab state (URL-persisted via `?subtab=`) ----------
const validSubtabs = ["saves", "states"] as const;
type Subtab = (typeof validSubtabs)[number];

const route = useRoute();
const router = useRouter();

const subTab = ref<Subtab>(
  validSubtabs.includes(route.query.subtab as Subtab)
    ? (route.query.subtab as Subtab)
    : "saves",
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
// When the user navigates away from this tab, drop the subtab param
// so it doesn't leak onto sibling tabs.
watch(
  () => route.query.tab,
  (value) => {
    if (value !== "save-data" && route.query.subtab) {
      const rest = { ...route.query };
      delete rest.subtab;
      router.replace({ path: route.path, query: rest });
    }
  },
);

const authStore = storeAuth();
const { user } = storeToRefs(authStore);
const myId = computed(() => user.value?.id ?? null);

function isOwn(asset: { user_id: number }): boolean {
  return myId.value != null && asset.user_id === myId.value;
}

// `all_user_{saves,states}` holds own (public + private) plus other users'
// public items. Split into Mine / Community the same way ScreenshotsSubtab does.
const allSaves = computed<UserSaveSchema[]>(
  () => props.rom.all_user_saves ?? [],
);
const allStates = computed<UserStateSchema[]>(
  () => props.rom.all_user_states ?? [],
);

const mySaves = computed(() => allSaves.value.filter(isOwn));
const communitySaves = computed(() => allSaves.value.filter((s) => !isOwn(s)));
const myStates = computed(() => allStates.value.filter(isOwn));
const communityStates = computed(() =>
  allStates.value.filter((s) => !isOwn(s)),
);

// Badge = total visible items in the subtab (own + community).
const savesCount = computed(() => allSaves.value.length);
const statesCount = computed(() => allStates.value.length);

// ---------- Subtab nav definitions ----------
type SubtabDef = { id: Subtab; label: string; icon: string };
const subtabDefs = computed<SubtabDef[]>(() => [
  { id: "saves", label: t("rom.saves-tab"), icon: "mdi-content-save-outline" },
  { id: "states", label: t("rom.states-tab"), icon: "mdi-camera-outline" },
]);

// ---------- Upload / refresh plumbing ----------
// Overlay-mode dropzone refs so the section-header "Upload" buttons can
// open the native picker via `.open()`; the empty-state CTA dropzones
// are self-contained (click-to-browse + drag-and-drop).
const saveDz = ref<InstanceType<typeof RDropzone> | null>(null);
const stateDz = ref<InstanceType<typeof RDropzone> | null>(null);
const uploadingSaves = ref(false);
const uploadingStates = ref(false);

const snackbar = useSnackbar();
const confirm = useConfirm();
const romsStore = storeRoms();

function errorMessage(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const detail = err.response?.data?.detail;
    if (typeof detail === "string" && detail) return detail;
    return err.message;
  }
  return err instanceof Error ? err.message : String(err);
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

async function onSaveUpload(files: File[]) {
  if (files.length === 0 || uploadingSaves.value) return;

  uploadingSaves.value = true;
  try {
    const results = await saveApi.uploadSaves({
      rom: props.rom,
      savesToUpload: files.map((saveFile) => ({ saveFile })),
    });
    const successful = results.filter((r) => r.status === "fulfilled").length;
    const failed = results.length - successful;

    if (successful > 0) {
      snackbar.success(
        failed
          ? t("rom.saves-uploaded-with-failed", successful, {
              named: { n: successful, failed },
            })
          : t("rom.saves-uploaded-n", successful, {
              named: { n: successful },
            }),
        { icon: "mdi-check-bold" },
      );
      await refreshRom();
    } else {
      snackbar.warning(t("rom.no-saves-uploaded"), {
        icon: "mdi-close-circle",
      });
    }
  } finally {
    uploadingSaves.value = false;
  }
}

async function onStateUpload(files: File[]) {
  if (files.length === 0 || uploadingStates.value) return;

  uploadingStates.value = true;
  try {
    const results = await stateApi.uploadStates({
      rom: props.rom,
      statesToUpload: files.map((stateFile) => ({ stateFile })),
    });
    const successful = results.filter((r) => r.status === "fulfilled").length;
    const failed = results.length - successful;

    if (successful > 0) {
      snackbar.success(
        failed
          ? t("rom.states-uploaded-with-failed", successful, {
              named: { n: successful, failed },
            })
          : t("rom.states-uploaded-n", successful, {
              named: { n: successful },
            }),
        { icon: "mdi-check-bold" },
      );
      await refreshRom();
    } else {
      snackbar.warning(t("rom.no-states-uploaded"), {
        icon: "mdi-close-circle",
      });
    }
  } finally {
    uploadingStates.value = false;
  }
}

// ---------- Per-row actions ----------
// Both saves and states ship `download_path` from the backend — fire
// a synthesized anchor click rather than a window.open so the browser
// uses the right filename and skips the new-tab affordance.
function downloadAsset(asset: { download_path: string; file_name: string }) {
  const a = document.createElement("a");
  a.href = asset.download_path;
  a.download = asset.file_name;
  document.body.appendChild(a);
  a.click();
  a.remove();
}

async function deleteSave(save: SaveSchema) {
  const ok = await confirm({
    title: t("rom.delete-save-title"),
    body: t("rom.delete-save-body-named", { name: save.file_name }),
    confirmText: t("rom.delete-save"),
    tone: "danger",
  });
  if (!ok) return;
  try {
    await saveApi.deleteSaves({ saves: [save] });
    snackbar.success(t("rom.save-deleted"), { icon: "mdi-check-bold" });
    await refreshRom();
  } catch (error) {
    snackbar.error(t("rom.cant-delete-save", { error: errorMessage(error) }), {
      icon: "mdi-close-circle",
    });
  }
}

async function deleteState(state: StateSchema) {
  const ok = await confirm({
    title: t("rom.delete-state-title"),
    body: t("rom.delete-state-body-named", { name: state.file_name }),
    confirmText: t("rom.delete-state"),
    tone: "danger",
  });
  if (!ok) return;
  try {
    await stateApi.deleteStates({ states: [state] });
    snackbar.success(t("rom.state-deleted"), { icon: "mdi-check-bold" });
    await refreshRom();
  } catch (error) {
    snackbar.error(t("rom.cant-delete-state", { error: errorMessage(error) }), {
      icon: "mdi-close-circle",
    });
  }
}

// ---------- Visibility toggle (own items only) ----------
const togglingSaveId = ref<number | null>(null);
const togglingStateId = ref<number | null>(null);

async function toggleSaveVisibility(save: SaveSchema) {
  if (togglingSaveId.value != null) return;
  togglingSaveId.value = save.id;
  try {
    await saveApi.setSaveVisibility({ id: save.id, isPublic: !save.is_public });
    await refreshRom();
  } catch (error) {
    snackbar.error(
      t("rom.cant-toggle-visibility", { error: errorMessage(error) }),
      { icon: "mdi-close-circle" },
    );
  } finally {
    togglingSaveId.value = null;
  }
}

async function toggleStateVisibility(state: StateSchema) {
  if (togglingStateId.value != null) return;
  togglingStateId.value = state.id;
  try {
    await stateApi.setStateVisibility({
      id: state.id,
      isPublic: !state.is_public,
    });
    await refreshRom();
  } catch (error) {
    snackbar.error(
      t("rom.cant-toggle-visibility", { error: errorMessage(error) }),
      { icon: "mdi-close-circle" },
    );
  } finally {
    togglingStateId.value = null;
  }
}
</script>

<template>
  <div class="r-v2-saves">
    <aside class="r-v2-saves__sidebar">
      <ul
        class="r-v2-saves__subtabs"
        role="tablist"
        aria-orientation="vertical"
      >
        <li v-for="tab in subtabDefs" :key="tab.id" class="r-v2-saves__subtab">
          <button
            type="button"
            role="tab"
            class="r-v2-saves__subtab-btn"
            :class="{
              'r-v2-saves__subtab-btn--active': subTab === tab.id,
            }"
            :aria-selected="subTab === tab.id"
            @click="subTab = tab.id"
          >
            <RIcon :icon="tab.icon" size="16" />
            <span class="r-v2-saves__subtab-label">{{ tab.label }}</span>
            <span
              v-if="
                (tab.id === 'saves' && savesCount) ||
                (tab.id === 'states' && statesCount)
              "
              class="r-v2-saves__subtab-badge"
            >
              {{ tab.id === "saves" ? savesCount : statesCount }}
            </span>
          </button>
        </li>
      </ul>
    </aside>

    <div class="r-v2-saves__content">
      <!-- Saves subtab — vertical info list -->
      <section v-show="subTab === 'saves'" class="r-v2-saves__panel">
        <!-- Mine -->
        <div class="r-v2-saves__section">
          <header class="r-v2-saves__section-head">
            <div class="r-v2-saves__section-head-text">
              <h3 class="r-v2-saves__section-title">
                {{ t("rom.saves-section-mine") }}
              </h3>
            </div>
            <RBtn
              v-if="mySaves.length > 0"
              variant="outlined"
              size="small"
              prepend-icon="mdi-cloud-upload-outline"
              :loading="uploadingSaves"
              :disabled="uploadingSaves"
              @click="saveDz?.open()"
            >
              {{ t("common.upload") }}
            </RBtn>
          </header>

          <RDropzone
            v-if="mySaves.length === 0"
            :title="t('rom.saves-empty')"
            :hint="t('common.dropzone-hint')"
            :active-title="t('common.dropzone-drag-over')"
            :input-label="t('rom.upload-saves')"
            :disabled="uploadingSaves"
            multiple
            @files="onSaveUpload"
          />

          <RDropzone
            v-else
            ref="saveDz"
            overlay
            :release-label="t('common.dropzone-drag-over')"
            :input-label="t('rom.upload-saves')"
            :disabled="uploadingSaves"
            multiple
            @files="onSaveUpload"
          >
            <AssetList
              :assets="mySaves"
              type="save"
              :selectable="false"
              :scrollable="false"
            >
              <template #actions="{ asset }">
                <RBtn
                  :icon="asset.is_public ? 'mdi-lock-open-variant' : 'mdi-lock'"
                  variant="text"
                  size="small"
                  :color="
                    asset.is_public ? 'var(--r-color-fg-muted)' : 'primary'
                  "
                  :loading="togglingSaveId === asset.id"
                  :tooltip="
                    asset.is_public
                      ? t('rom.make-private')
                      : t('rom.make-public')
                  "
                  :aria-label="
                    asset.is_public
                      ? t('rom.make-private')
                      : t('rom.make-public')
                  "
                  @click="toggleSaveVisibility(asSave(asset))"
                />
                <RBtn
                  icon="mdi-download-outline"
                  variant="text"
                  size="small"
                  :tooltip="t('common.download')"
                  :aria-label="
                    t('rom.download-named', { name: asset.file_name })
                  "
                  @click="downloadAsset(asset)"
                />
                <RBtn
                  icon="mdi-delete-outline"
                  variant="text"
                  size="small"
                  color="romm-red"
                  :tooltip="t('common.delete')"
                  :aria-label="t('rom.delete-save')"
                  @click="deleteSave(asSave(asset))"
                />
              </template>
            </AssetList>
          </RDropzone>
        </div>

        <!-- Community -->
        <div v-if="communitySaves.length > 0" class="r-v2-saves__section">
          <header class="r-v2-saves__section-head">
            <div class="r-v2-saves__section-head-text">
              <h3 class="r-v2-saves__section-title">
                {{ t("rom.saves-section-community") }}
              </h3>
            </div>
          </header>
          <AssetList
            :assets="communitySaves"
            type="save"
            :selectable="false"
            :scrollable="false"
            show-owner
          >
            <template #actions="{ asset }">
              <RBtn
                icon="mdi-download-outline"
                variant="text"
                size="small"
                :tooltip="t('common.download')"
                :aria-label="t('rom.download-named', { name: asset.file_name })"
                @click="downloadAsset(asset)"
              />
            </template>
          </AssetList>
        </div>
      </section>

      <!-- States subtab — tile grid (screenshot is the point) -->
      <section v-show="subTab === 'states'" class="r-v2-saves__panel">
        <!-- Mine -->
        <div class="r-v2-saves__section">
          <header class="r-v2-saves__section-head">
            <div class="r-v2-saves__section-head-text">
              <h3 class="r-v2-saves__section-title">
                {{ t("rom.states-section-mine") }}
              </h3>
            </div>
            <RBtn
              v-if="myStates.length > 0"
              variant="outlined"
              size="small"
              prepend-icon="mdi-cloud-upload-outline"
              :loading="uploadingStates"
              :disabled="uploadingStates"
              @click="stateDz?.open()"
            >
              {{ t("common.upload") }}
            </RBtn>
          </header>

          <RDropzone
            v-if="myStates.length === 0"
            :title="t('rom.states-empty')"
            :hint="t('common.dropzone-hint')"
            :active-title="t('common.dropzone-drag-over')"
            :input-label="t('rom.upload-states')"
            :disabled="uploadingStates"
            multiple
            @files="onStateUpload"
          />

          <RDropzone
            v-else
            ref="stateDz"
            overlay
            :release-label="t('common.dropzone-drag-over')"
            :input-label="t('rom.upload-states')"
            :disabled="uploadingStates"
            multiple
            @files="onStateUpload"
          >
            <AssetStrip
              :assets="myStates"
              type="state"
              :selectable="false"
              layout="flow"
            >
              <template #actions="{ asset }">
                <RBtn
                  :icon="asset.is_public ? 'mdi-lock-open-variant' : 'mdi-lock'"
                  variant="text"
                  size="small"
                  :color="
                    asset.is_public ? 'var(--r-color-fg-muted)' : 'primary'
                  "
                  :loading="togglingStateId === asset.id"
                  :tooltip="
                    asset.is_public
                      ? t('rom.make-private')
                      : t('rom.make-public')
                  "
                  :aria-label="
                    asset.is_public
                      ? t('rom.make-private')
                      : t('rom.make-public')
                  "
                  @click="toggleStateVisibility(asState(asset))"
                />
                <RBtn
                  icon="mdi-download-outline"
                  variant="text"
                  size="small"
                  :tooltip="t('common.download')"
                  :aria-label="
                    t('rom.download-named', { name: asset.file_name })
                  "
                  @click="downloadAsset(asset)"
                />
                <RBtn
                  icon="mdi-delete-outline"
                  variant="text"
                  size="small"
                  color="romm-red"
                  :tooltip="t('common.delete')"
                  :aria-label="t('rom.delete-state')"
                  @click="deleteState(asState(asset))"
                />
              </template>
            </AssetStrip>
          </RDropzone>
        </div>

        <!-- Community -->
        <div v-if="communityStates.length > 0" class="r-v2-saves__section">
          <header class="r-v2-saves__section-head">
            <div class="r-v2-saves__section-head-text">
              <h3 class="r-v2-saves__section-title">
                {{ t("rom.states-section-community") }}
              </h3>
            </div>
          </header>
          <AssetStrip
            :assets="communityStates"
            type="state"
            :selectable="false"
            layout="flow"
            show-owner
          >
            <template #actions="{ asset }">
              <RBtn
                icon="mdi-download-outline"
                variant="text"
                size="small"
                :tooltip="t('common.download')"
                :aria-label="t('rom.download-named', { name: asset.file_name })"
                @click="downloadAsset(asset)"
              />
            </template>
          </AssetStrip>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.r-v2-saves {
  display: flex;
  align-items: stretch;
  gap: 24px;
  height: 100%;
  min-height: 0;
}

.r-v2-saves__sidebar {
  width: 220px;
  flex-shrink: 0;
}

/* Subtab list — navigation only. Per-section actions (Upload) live
   in the content column's section headers, not under the sidebar. */
.r-v2-saves__subtabs {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.r-v2-saves__subtab {
  display: flex;
  flex-direction: column;
}
.r-v2-saves__subtab-btn {
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
.r-v2-saves__subtab-btn:hover {
  background: var(--r-color-surface-hover);
  color: var(--r-color-fg);
}
.r-v2-saves__subtab-btn--active {
  background: color-mix(in srgb, var(--r-color-brand-primary) 18%, transparent);
  color: var(--r-color-brand-primary);
}
.r-v2-saves__subtab-label {
  flex: 1;
}
.r-v2-saves__subtab-badge {
  font-size: 10px;
  font-weight: var(--r-font-weight-bold);
  padding: 1px 7px;
  border-radius: 999px;
  background: color-mix(in srgb, currentColor 18%, transparent);
}

.r-v2-saves__content {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.r-v2-saves__panel {
  display: flex;
  flex-direction: column;
  gap: var(--r-space-5);
  flex: 1;
  min-height: 0;
}

/* Mine / Community subsections within a subtab panel. Header layout
   mirrors ScreenshotsSubtab: title on the left, Upload button on the
   right when the section already has items. */
.r-v2-saves__section {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.r-v2-saves__section-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}
.r-v2-saves__section-title {
  margin: 0;
  font-size: 14px;
  font-weight: var(--r-font-weight-semibold);
  color: var(--r-color-fg);
}

html[data-bp~="xs"] .r-v2-saves {
  flex-direction: column;
  gap: 14px;
}
html[data-bp~="xs"] .r-v2-saves__sidebar {
  width: auto;
}
</style>
