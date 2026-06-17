<script setup lang="ts">
// SaveDataTab — Saves + States, each its own subtab with badge counts
// and per-tab Upload affordance. Layout mirrors MediaTab: a vertical
// subtab list on the left with an attached RCollapsible action panel
// underneath the active tab, and the file list filling the content
// column on the right. Per-row Download + Delete actions are
// always-visible icon buttons; empty states promote the Upload CTA.
//
// URL-persistent subtab selection via `?subtab=` so deep-linking
// into a specific list works and stale state doesn't leak when the
// user navigates to a sibling tab.
import { RBtn, RCollapsible, REmptyState, RIcon } from "@v2/lib";
import axios from "axios";
import { computed, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute, useRouter } from "vue-router";
import type {
  DetailedRomSchema,
  SaveSchema,
  StateSchema,
} from "@/__generated__";
import romApi from "@/services/api/rom";
import saveApi from "@/services/api/save";
import stateApi from "@/services/api/state";
import storeRoms from "@/stores/roms";
import { formatBytes } from "@/utils";
import { useConfirm } from "@/v2/composables/useConfirm";
import { useSnackbar } from "@/v2/composables/useSnackbar";

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

const saves = computed<SaveSchema[]>(() => props.rom.user_saves ?? []);
const states = computed<StateSchema[]>(() => props.rom.user_states ?? []);

// ---------- Subtab nav definitions ----------
type SubtabDef = { id: Subtab; label: string; icon: string };
const subtabDefs = computed<SubtabDef[]>(() => [
  { id: "saves", label: t("rom.saves-tab"), icon: "mdi-content-save-outline" },
  { id: "states", label: t("rom.states-tab"), icon: "mdi-camera-outline" },
]);

// Inline action panel under the active subtab only renders when the
// list has entries — empty states own the Upload CTA so there's no
// redundant panel.
function hasSubtabActions(id: Subtab): boolean {
  return id === "saves" ? saves.value.length > 0 : states.value.length > 0;
}

// ---------- Upload / refresh plumbing ----------
const saveUploadInput = ref<HTMLInputElement | null>(null);
const stateUploadInput = ref<HTMLInputElement | null>(null);
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

function triggerSaveUpload() {
  saveUploadInput.value?.click();
}
function triggerStateUpload() {
  stateUploadInput.value?.click();
}

async function onSaveUpload(event: Event) {
  const input = event.target as HTMLInputElement;
  const files = input.files ? Array.from(input.files) : [];
  input.value = "";
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
          ? t("rom.saves-uploaded-with-failed", { n: successful, failed })
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

async function onStateUpload(event: Event) {
  const input = event.target as HTMLInputElement;
  const files = input.files ? Array.from(input.files) : [];
  input.value = "";
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
          ? t("rom.states-uploaded-with-failed", { n: successful, failed })
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

function fmtDate(iso: string | null) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString();
}
</script>

<template>
  <!-- Hidden file inputs drive the Upload buttons (mirroring MediaTab) -->
  <input
    ref="saveUploadInput"
    type="file"
    multiple
    class="r-v2-saves__file-input"
    :aria-label="t('rom.upload-saves')"
    @change="onSaveUpload"
  />
  <input
    ref="stateUploadInput"
    type="file"
    multiple
    class="r-v2-saves__file-input"
    :aria-label="t('rom.upload-states')"
    @change="onStateUpload"
  />

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
              'r-v2-saves__subtab-btn--joined':
                subTab === tab.id && hasSubtabActions(tab.id),
            }"
            :aria-selected="subTab === tab.id"
            @click="subTab = tab.id"
          >
            <RIcon :icon="tab.icon" size="16" />
            <span class="r-v2-saves__subtab-label">{{ tab.label }}</span>
            <span
              v-if="
                (tab.id === 'saves' && saves.length) ||
                (tab.id === 'states' && states.length)
              "
              class="r-v2-saves__subtab-badge"
            >
              {{ tab.id === "saves" ? saves.length : states.length }}
            </span>
          </button>

          <RCollapsible
            :model-value="subTab === tab.id && hasSubtabActions(tab.id)"
            attached
            class="r-v2-saves__subtab-panel"
          >
            <div class="r-v2-saves__subtab-panel-inner">
              <template v-if="tab.id === 'saves' && saves.length > 0">
                <RBtn
                  variant="outlined"
                  prepend-icon="mdi-cloud-upload-outline"
                  block
                  :loading="uploadingSaves"
                  :disabled="uploadingSaves"
                  @click="triggerSaveUpload"
                >
                  {{ t("common.upload") }}
                </RBtn>
              </template>
              <template v-else-if="tab.id === 'states' && states.length > 0">
                <RBtn
                  variant="outlined"
                  prepend-icon="mdi-cloud-upload-outline"
                  block
                  :loading="uploadingStates"
                  :disabled="uploadingStates"
                  @click="triggerStateUpload"
                >
                  {{ t("common.upload") }}
                </RBtn>
              </template>
            </div>
          </RCollapsible>
        </li>
      </ul>
    </aside>

    <div class="r-v2-saves__content">
      <!-- Saves subtab -->
      <section v-show="subTab === 'saves'" class="r-v2-saves__panel">
        <REmptyState
          v-if="saves.length === 0"
          icon="mdi-content-save-outline"
          :title="t('rom.saves-empty')"
          :hint="t('rom.saves-empty-hint')"
        >
          <template #actions>
            <RBtn
              color="primary"
              prepend-icon="mdi-cloud-upload-outline"
              :loading="uploadingSaves"
              :disabled="uploadingSaves"
              @click="triggerSaveUpload"
            >
              {{ t("rom.upload-saves") }}
            </RBtn>
          </template>
        </REmptyState>

        <ul v-else class="r-v2-saves__list">
          <li v-for="s in saves" :key="s.id" class="r-v2-saves__row">
            <div class="r-v2-saves__row-main">
              <div class="r-v2-saves__row-name">{{ s.file_name }}</div>
              <div class="r-v2-saves__row-meta">
                <span>{{ formatBytes(s.file_size_bytes) }}</span>
                <span class="r-v2-saves__sep">·</span>
                <span>{{ fmtDate(s.updated_at) }}</span>
                <template v-if="s.emulator">
                  <span class="r-v2-saves__sep">·</span>
                  <span>{{ s.emulator }}</span>
                </template>
              </div>
            </div>
            <div class="r-v2-saves__row-actions">
              <RBtn
                icon="mdi-download-outline"
                variant="text"
                size="small"
                :tooltip="t('common.download')"
                :aria-label="t('rom.download-named', { name: s.file_name })"
                @click="downloadAsset(s)"
              />
              <RBtn
                icon="mdi-delete-outline"
                variant="text"
                size="small"
                color="romm-red"
                :tooltip="t('common.delete')"
                :aria-label="t('rom.delete-save')"
                @click="deleteSave(s)"
              />
            </div>
          </li>
        </ul>
      </section>

      <!-- States subtab -->
      <section v-show="subTab === 'states'" class="r-v2-saves__panel">
        <REmptyState
          v-if="states.length === 0"
          icon="mdi-camera-outline"
          :title="t('rom.states-empty')"
          :hint="t('rom.states-empty-hint')"
        >
          <template #actions>
            <RBtn
              color="primary"
              prepend-icon="mdi-cloud-upload-outline"
              :loading="uploadingStates"
              :disabled="uploadingStates"
              @click="triggerStateUpload"
            >
              {{ t("rom.upload-states") }}
            </RBtn>
          </template>
        </REmptyState>

        <ul v-else class="r-v2-saves__list">
          <li v-for="s in states" :key="s.id" class="r-v2-saves__row">
            <div class="r-v2-saves__row-main">
              <div class="r-v2-saves__row-name">{{ s.file_name }}</div>
              <div class="r-v2-saves__row-meta">
                <span>{{ formatBytes(s.file_size_bytes) }}</span>
                <span class="r-v2-saves__sep">·</span>
                <span>{{ fmtDate(s.updated_at) }}</span>
                <template v-if="s.emulator">
                  <span class="r-v2-saves__sep">·</span>
                  <span>{{ s.emulator }}</span>
                </template>
              </div>
            </div>
            <div class="r-v2-saves__row-actions">
              <RBtn
                icon="mdi-download-outline"
                variant="text"
                size="small"
                :tooltip="t('common.download')"
                :aria-label="t('rom.download-named', { name: s.file_name })"
                @click="downloadAsset(s)"
              />
              <RBtn
                icon="mdi-delete-outline"
                variant="text"
                size="small"
                color="romm-red"
                :tooltip="t('common.delete')"
                :aria-label="t('rom.delete-state')"
                @click="deleteState(s)"
              />
            </div>
          </li>
        </ul>
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

/* Subtab list — inline-expansion pattern: each tab can host a panel
   of contextual actions right under its button. Visually identical
   to MediaTab so the two GameDetails tabs share the same vocabulary. */
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
.r-v2-saves__subtab-btn--joined {
  border-bottom-left-radius: 0;
  border-bottom-right-radius: 0;
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

/* Inline action panel — RCollapsible (attached, headless) provides
   the surface (bg-elevated + border + bottom radius) and the open /
   close animation. We add inner padding here so the controls breathe
   inside the panel. */
.r-v2-saves__subtab-panel {
  margin-bottom: var(--r-space-1);
}
.r-v2-saves__subtab-panel-inner {
  display: flex;
  flex-direction: column;
  gap: var(--r-space-2);
  padding: var(--r-space-3);
}

.r-v2-saves__content {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.r-v2-saves__file-input {
  display: none;
}

.r-v2-saves__panel {
  display: flex;
  flex-direction: column;
  gap: var(--r-space-3);
  flex: 1;
  min-height: 0;
}

/* File-list rows. The trailing action cluster only paints buttons —
   no border or background — because the row itself owns the surface. */
.r-v2-saves__list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  list-style: none;
  margin: 0;
  padding: 0;
}

.r-v2-saves__row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  background: var(--r-color-bg-elevated);
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-md);
  color: var(--r-color-fg);
}
.r-v2-saves__row > .mdi {
  color: var(--r-color-fg-muted);
}

.r-v2-saves__row-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.r-v2-saves__row-name {
  font-size: 13px;
  font-weight: var(--r-font-weight-medium);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.r-v2-saves__row-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11.5px;
  color: var(--r-color-fg-muted);
  flex-wrap: wrap;
}
.r-v2-saves__sep {
  opacity: 0.5;
}

.r-v2-saves__row-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

html[data-bp~="xs"] .r-v2-saves {
  flex-direction: column;
  gap: 14px;
}
html[data-bp~="xs"] .r-v2-saves__sidebar {
  width: auto;
}
</style>
