<script setup lang="ts">
// SaveDataTab: Saves + States, each its own subtab with badge counts and an
// Upload affordance. A vertical subtab list sits on the left (a picker row
// on phones), and each "Mine" section header carries Upload once it has
// items; empty sections promote the dropzone CTA instead.
//
// Each list is split into a "Mine" section (own saves/states, with a
// per-item public/private toggle + delete) and a read-only "Community"
// section (other users' public saves/states, with an author chip and
// download only). Mirrors ScreenshotsSubtab's My / Community model.
//
// URL-persistent subtab selection via `?subtab=` so deep-linking
// into a specific list works and stale state doesn't leak when the
// user navigates to a sibling tab.
import { RBtn, RDropzone } from "@v2/lib";
import { storeToRefs } from "pinia";
import { computed, ref } from "vue";
import { useI18n } from "vue-i18n";
import type {
  DetailedRomSchema,
  SaveSchema,
  StateSchema,
  UserSaveSchema,
  UserStateSchema,
} from "@/__generated__";
import saveApi from "@/services/api/save";
import stateApi from "@/services/api/state";
import storeAuth from "@/stores/auth";
import storeConfig from "@/stores/config";
import { getSupportedEJSCores } from "@/utils";
import AssetActions from "@/v2/components/GameDetails/AssetActions.vue";
import SubtabNav, {
  type SubtabNavItem,
} from "@/v2/components/GameDetails/SubtabNav.vue";
import UploadAssetDialog, {
  type UploadAssetPayload,
} from "@/v2/components/GameDetails/UploadAssetDialog.vue";
import AssetList from "@/v2/components/shared/AssetList.vue";
import AssetStrip from "@/v2/components/shared/AssetStrip.vue";
import { useBreakpoint } from "@/v2/composables/useBreakpoint";
import { useConfirm } from "@/v2/composables/useConfirm";
import { useRomSync } from "@/v2/composables/useRomSync";
import { useSnackbar } from "@/v2/composables/useSnackbar";
import { useSubtabQuery } from "@/v2/composables/useSubtabQuery";
import type { AssetType } from "@/v2/utils/assets";
import { errorMessage } from "@/v2/utils/errorMessage";

// Slot payload from AssetList/AssetStrip is the full save|state union; these
// narrow it back to the concrete schema the section's handlers expect.
type AssetSlot = SaveSchema | StateSchema | UserSaveSchema | UserStateSchema;
const asSave = (a: AssetSlot) => a as SaveSchema;
const asState = (a: AssetSlot) => a as StateSchema;

defineOptions({ inheritAttrs: false });

const props = defineProps<{ rom: DetailedRomSchema }>();
const { t } = useI18n();
const { smAndDown } = useBreakpoint();

// ---------- Subtab state (URL-persisted via `?subtab=`) ----------
const validSubtabs = ["saves", "states"] as const;
type Subtab = (typeof validSubtabs)[number];

const subTab = useSubtabQuery<Subtab>(
  "save-data",
  (value) => validSubtabs.includes(value as Subtab),
  "saves",
);

const authStore = storeAuth();
const configStore = storeConfig();
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
const subtabDefs = computed<SubtabNavItem<Subtab>[]>(() => [
  {
    id: "saves",
    label: t("rom.saves-tab"),
    icon: "mdi-content-save-outline",
    badge: savesCount.value,
  },
  {
    id: "states",
    label: t("rom.states-tab"),
    icon: "mdi-camera-outline",
    badge: statesCount.value,
  },
]);

// ---------- Upload / refresh plumbing ----------
// Every upload goes through the dialog, which asks saves for a slot and
// states for a core; dropped files land in it pre-picked.
const uploadDialog = ref<{ type: AssetType; files: File[] } | null>(null);
function openUpload(type: AssetType, files: File[] = []) {
  uploadDialog.value = { type, files };
}
function closeUpload() {
  uploadDialog.value = null;
}
// The cores the player offers plus whatever the existing states carry.
const uploadCores = computed(() => {
  const cores = new Set(
    getSupportedEJSCores(
      props.rom.platform_slug,
      configStore.config.EJS_NETPLAY_ENABLED,
    ),
  );
  for (const state of myStates.value) {
    if (state.emulator) cores.add(state.emulator);
  }
  return [...cores];
});
async function onUploadSubmit({
  type,
  files,
  slot,
  emulator,
}: UploadAssetPayload) {
  uploadDialog.value = null;
  if (type === "save") await onSaveUpload(files, slot);
  else await onStateUpload(files, emulator);
}
const uploadingSaves = ref(false);
const uploadingStates = ref(false);

// On phones the active subtab's Upload moves from the "Mine" section header
// into the subtab picker's row.
const pickerRowUpload = computed(() => {
  const saves = subTab.value === "saves";
  if ((saves ? mySaves : myStates).value.length === 0) return null;
  return saves
    ? { type: "save" as const, busy: uploadingSaves.value }
    : { type: "state" as const, busy: uploadingStates.value };
});

const snackbar = useSnackbar();
const confirm = useConfirm();
const { refetchRom } = useRomSync();

async function refreshRom() {
  await refetchRom(props.rom.id);
}

async function onSaveUpload(files: File[], slot: string | null) {
  if (files.length === 0 || uploadingSaves.value) return;

  uploadingSaves.value = true;
  try {
    // A manual upload into a slot is a new version even if the bytes match.
    const results = await saveApi.uploadSaves({
      rom: props.rom,
      savesToUpload: files.map((saveFile) => ({ saveFile })),
      slot: slot ?? undefined,
      overwrite: slot !== null,
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

async function onStateUpload(files: File[], emulator: string | null) {
  if (files.length === 0 || uploadingStates.value) return;

  uploadingStates.value = true;
  try {
    const results = await stateApi.uploadStates({
      rom: props.rom,
      statesToUpload: files.map((stateFile) => ({ stateFile })),
      emulator: emulator ?? undefined,
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
    <SubtabNav
      v-if="smAndDown"
      v-model="subTab"
      :items="subtabDefs"
      variant="menu"
    >
      <template #actions>
        <RBtn
          v-if="pickerRowUpload"
          variant="outlined"
          size="small"
          density="comfortable"
          prepend-icon="mdi-cloud-upload-outline"
          :loading="pickerRowUpload.busy"
          :disabled="pickerRowUpload.busy"
          @click="openUpload(pickerRowUpload.type)"
        >
          {{ t("common.upload") }}
        </RBtn>
      </template>
    </SubtabNav>
    <aside v-else class="r-v2-saves__sidebar">
      <SubtabNav v-model="subTab" :items="subtabDefs" />
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
              v-if="mySaves.length > 0 && !smAndDown"
              variant="outlined"
              size="small"
              prepend-icon="mdi-cloud-upload-outline"
              :loading="uploadingSaves"
              :disabled="uploadingSaves"
              @click="openUpload('save')"
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
            @files="openUpload('save', $event)"
          />

          <RDropzone
            v-else
            overlay
            :release-label="t('common.dropzone-drag-over')"
            :input-label="t('rom.upload-saves')"
            :disabled="uploadingSaves"
            multiple
            @files="openUpload('save', $event)"
          >
            <AssetList
              :assets="mySaves"
              type="save"
              :selectable="false"
              :scrollable="false"
            >
              <template #actions="{ asset }">
                <AssetActions
                  :asset="asset"
                  type="save"
                  own
                  :toggling="togglingSaveId === asset.id"
                  @toggle-visibility="toggleSaveVisibility(asSave(asset))"
                  @download="downloadAsset(asset)"
                  @delete="deleteSave(asSave(asset))"
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
              <AssetActions
                :asset="asset"
                type="save"
                @download="downloadAsset(asset)"
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
              v-if="myStates.length > 0 && !smAndDown"
              variant="outlined"
              size="small"
              prepend-icon="mdi-cloud-upload-outline"
              :loading="uploadingStates"
              :disabled="uploadingStates"
              @click="openUpload('state')"
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
            @files="openUpload('state', $event)"
          />

          <RDropzone
            v-else
            overlay
            :release-label="t('common.dropzone-drag-over')"
            :input-label="t('rom.upload-states')"
            :disabled="uploadingStates"
            multiple
            @files="openUpload('state', $event)"
          >
            <AssetStrip
              :assets="myStates"
              type="state"
              :selectable="false"
              layout="flow"
              group-by="emulator"
            >
              <template #actions="{ asset }">
                <AssetActions
                  :asset="asset"
                  type="state"
                  own
                  :toggling="togglingStateId === asset.id"
                  @toggle-visibility="toggleStateVisibility(asState(asset))"
                  @download="downloadAsset(asset)"
                  @delete="deleteState(asState(asset))"
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
            group-by="emulator"
            show-owner
          >
            <template #actions="{ asset }">
              <AssetActions
                :asset="asset"
                type="state"
                @download="downloadAsset(asset)"
              />
            </template>
          </AssetStrip>
        </div>
      </section>
    </div>

    <UploadAssetDialog
      :model-value="uploadDialog !== null"
      :type="uploadDialog?.type ?? 'save'"
      :saves="mySaves"
      :cores="uploadCores"
      :initial-files="uploadDialog?.files ?? []"
      @update:model-value="!$event && closeUpload()"
      @submit="onUploadSubmit"
    />
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

html[data-bp~="sm-and-down"] .r-v2-saves {
  flex-direction: column;
  gap: 14px;
}
</style>
