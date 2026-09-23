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
// into a specific list works.
import { RBtn, RDropzone } from "@v2/lib";
import { storeToRefs } from "pinia";
import { computed, ref, watch } from "vue";
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
import AssetLabelsDialog from "@/v2/components/GameDetails/AssetLabelsDialog.vue";
import AssetSelectionToolbar from "@/v2/components/GameDetails/AssetSelectionToolbar.vue";
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
import { useIdSelection } from "@/v2/composables/useIdSelection";
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

// ---------- Bulk selection (own items only) ----------
// A save and a state can share an id and both panels stay mounted, so each
// kind gets its own selection rather than one keyed by id alone.
const saveSelection = useIdSelection(() => mySaves.value);
const stateSelection = useIdSelection(() => myStates.value);

function selectionFor(type: AssetType) {
  return type === "save" ? saveSelection : stateSelection;
}

// A selection only makes sense against the list it was made on.
watch([subTab, () => props.rom.id], () => {
  saveSelection.clear();
  stateSelection.clear();
});

const allCheckedFavorite = (type: AssetType) => {
  const assets = selectionFor(type).selected.value;
  return assets.length > 0 && assets.every((a) => a.is_favorite);
};

// One bulk write at a time: each fans out a request per asset, so a second
// click would double the traffic and race the refresh.
const bulkBusy = ref(false);

/** Reports a fanned-out bulk write, which has no single-call route. */
async function reportBulk(
  results: PromiseSettledResult<unknown>[],
  okKey: string,
  failKey: string,
) {
  const ok = results.filter((r) => r.status === "fulfilled").length;
  if (ok > 0) {
    snackbar.success(t(okKey, ok, { named: { n: ok } }), {
      icon: "mdi-check-bold",
    });
  }
  const failed = results.find((r) => r.status === "rejected") as
    PromiseRejectedResult | undefined;
  if (failed) {
    snackbar.error(t(failKey, { error: errorMessage(failed.reason) }), {
      icon: "mdi-close-circle",
    });
  }
  await refreshRom();
}

async function toggleCheckedFavorite(type: AssetType) {
  const assets = selectionFor(type).selected.value;
  if (assets.length === 0 || bulkBusy.value) return;
  const isFavorite = !allCheckedFavorite(type);

  bulkBusy.value = true;
  try {
    const results = await Promise.allSettled(
      assets.map((asset) =>
        type === "save"
          ? saveApi.setSaveFavorite({ id: asset.id, isFavorite })
          : stateApi.setStateFavorite({ id: asset.id, isFavorite }),
      ),
    );
    await reportBulk(
      results,
      "rom.favorites-updated-n",
      "rom.cant-toggle-favorite",
    );
  } finally {
    bulkBusy.value = false;
  }
}

async function deleteChecked(type: AssetType) {
  const assets = selectionFor(type).selected.value;
  if (assets.length === 0 || bulkBusy.value) return;

  const ok = await confirm({
    title: t(
      type === "save" ? "rom.delete-saves-title" : "rom.delete-states-title",
      assets.length,
      { named: { n: assets.length } },
    ),
    body: t("rom.delete-assets-body"),
    confirmText: t("common.delete"),
    tone: "danger",
  });
  if (!ok) return;

  bulkBusy.value = true;
  try {
    if (type === "save") {
      await saveApi.deleteSaves({ saves: assets as SaveSchema[] });
    } else {
      await stateApi.deleteStates({ states: assets as StateSchema[] });
    }
    // Only once the rows are gone: a failed delete keeps them checked so the
    // user can retry without picking them again.
    selectionFor(type).clear();
    snackbar.success(
      t(
        type === "save" ? "rom.saves-deleted-n" : "rom.states-deleted-n",
        assets.length,
        { named: { n: assets.length } },
      ),
      { icon: "mdi-check-bold" },
    );
    await refreshRom();
  } catch (error) {
    snackbar.error(
      t(type === "save" ? "rom.cant-delete-save" : "rom.cant-delete-state", {
        error: errorMessage(error),
      }),
      { icon: "mdi-close-circle" },
    );
  } finally {
    bulkBusy.value = false;
  }
}

// ---------- Favorite and labels (own items only) ----------
// Keyed by type too: a save and a state can share an id.
const favoritingKey = ref<string | null>(null);
// Editing one asset replaces its labels; editing a selection adds to each,
// so a bulk edit can never wipe a label it did not show the user.
type LabelEdit =
  | { kind: "one"; type: AssetType; asset: AssetSlot }
  | { kind: "many"; type: AssetType };
const labelTarget = ref<LabelEdit | null>(null);
const savingLabels = ref(false);

function isFavoriting(type: AssetType, asset: AssetSlot): boolean {
  return favoritingKey.value === `${type}:${asset.id}`;
}

async function toggleFavorite(type: AssetType, asset: AssetSlot) {
  if (favoritingKey.value != null) return;
  favoritingKey.value = `${type}:${asset.id}`;
  const isFavorite = !asset.is_favorite;
  try {
    if (type === "save") {
      await saveApi.setSaveFavorite({ id: asset.id, isFavorite });
    } else {
      await stateApi.setStateFavorite({ id: asset.id, isFavorite });
    }
    await refreshRom();
  } catch (error) {
    snackbar.error(
      t("rom.cant-toggle-favorite", { error: errorMessage(error) }),
      { icon: "mdi-close-circle" },
    );
  } finally {
    favoritingKey.value = null;
  }
}

function writeLabels(type: AssetType, id: number, labels: string[]) {
  return type === "save"
    ? saveApi.setSaveLabels({ id, labels })
    : stateApi.setStateLabels({ id, labels });
}

async function submitLabels(labels: string[]) {
  const target = labelTarget.value;
  if (!target || savingLabels.value) return;
  savingLabels.value = true;
  try {
    if (target.kind === "one") {
      await writeLabels(target.type, target.asset.id, labels);
      await refreshRom();
      snackbar.success(t("rom.labels-updated"), { icon: "mdi-check-bold" });
    } else {
      const assets = selectionFor(target.type).selected.value;
      const results = await Promise.allSettled(
        assets.map((asset) =>
          writeLabels(target.type, asset.id, [
            ...new Set([...(asset.labels ?? []), ...labels]),
          ]),
        ),
      );
      await reportBulk(
        results,
        "rom.labels-applied-n",
        "rom.cant-update-labels",
      );
    }
    // Escape closes the dialog mid-save, so a slow write must not shut the
    // editor the user has since opened on another asset.
    if (labelTarget.value === target) labelTarget.value = null;
  } catch (error) {
    snackbar.error(
      t("rom.cant-update-labels", { error: errorMessage(error) }),
      {
        icon: "mdi-close-circle",
      },
    );
  } finally {
    savingLabels.value = false;
  }
}

// Every label the user already put on this ROM, so an edit reuses one instead
// of coining a near-duplicate. Community items carry none: labels are private.
const labelSuggestions = computed(() =>
  [
    ...new Set(
      [...mySaves.value, ...myStates.value].flatMap((a) => a.labels ?? []),
    ),
  ].sort((a, b) => a.localeCompare(b)),
);
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
            <AssetSelectionToolbar
              v-if="mySaves.length > 0"
              :count="saveSelection.count.value"
              :total="mySaves.length"
              :all-checked="saveSelection.allSelected.value"
              :some-checked="saveSelection.someSelected.value"
              :all-favorite="allCheckedFavorite('save')"
              @toggle-all="saveSelection.toggleAll()"
              @toggle-favorite="toggleCheckedFavorite('save')"
              @edit-labels="labelTarget = { kind: 'many', type: 'save' }"
              @delete="deleteChecked('save')"
              @clear="saveSelection.clear()"
            />
            <AssetList
              :assets="mySaves"
              type="save"
              :selectable="false"
              :scrollable="false"
              checkable
              :checked-ids="saveSelection.selectedIds.value"
              @toggle="saveSelection.toggle($event.id)"
            >
              <template #actions="{ asset }">
                <AssetActions
                  :asset="asset"
                  type="save"
                  own
                  :toggling="togglingSaveId === asset.id"
                  :favoriting="isFavoriting('save', asset)"
                  @toggle-favorite="toggleFavorite('save', asset)"
                  @edit-labels="
                    labelTarget = { kind: 'one', type: 'save', asset }
                  "
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
            <AssetSelectionToolbar
              v-if="myStates.length > 0"
              :count="stateSelection.count.value"
              :total="myStates.length"
              :all-checked="stateSelection.allSelected.value"
              :some-checked="stateSelection.someSelected.value"
              :all-favorite="allCheckedFavorite('state')"
              @toggle-all="stateSelection.toggleAll()"
              @toggle-favorite="toggleCheckedFavorite('state')"
              @edit-labels="labelTarget = { kind: 'many', type: 'state' }"
              @delete="deleteChecked('state')"
              @clear="stateSelection.clear()"
            />
            <AssetStrip
              :assets="myStates"
              type="state"
              :selectable="false"
              checkable
              :checked-ids="stateSelection.selectedIds.value"
              layout="flow"
              group-by="emulator"
              @toggle="stateSelection.toggle($event.id)"
            >
              <template #actions="{ asset }">
                <AssetActions
                  :asset="asset"
                  type="state"
                  own
                  :toggling="togglingStateId === asset.id"
                  :favoriting="isFavoriting('state', asset)"
                  @toggle-favorite="toggleFavorite('state', asset)"
                  @edit-labels="
                    labelTarget = { kind: 'one', type: 'state', asset }
                  "
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

    <AssetLabelsDialog
      :model-value="labelTarget !== null"
      :initial-labels="
        labelTarget?.kind === 'one' ? (labelTarget.asset.labels ?? []) : []
      "
      :title="labelTarget?.kind === 'many' ? t('rom.add-labels') : undefined"
      :suggestions="labelSuggestions"
      :busy="savingLabels"
      @update:model-value="!$event && (labelTarget = null)"
      @submit="submitLabels"
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
