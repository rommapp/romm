<script setup lang="ts">
// MemoryCardManager: manages the caller's own whole memory cards for one
// emulator. Rename, share (public toggle), delete, and browse per-card
// version history. Shared surface, mounted two ways:
//   1. In an RDialog opened from MemoryCardPicker's gear (in the play flow).
//   2. As the gated "Memory cards" tab on the platform page.
//
// Cards key HARD on `emulator`; `platformId` is only a creation/display hint.
// All routes here are `me`-scoped (own cards), so no permission gating beyond
// being signed in. Deleting a card also removes its version archives from the
// filesystem, so delete is a typed-confirm destructive action.
import { RBtn, RChip, REmptyState, RIcon, RSpinner, RSwitch } from "@v2/lib";
import { computed, reactive, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import type {
  MemoryCardSchema,
  MemoryCardVersionSchema,
} from "@/__generated__";
import memoryCardApi from "@/services/api/memory-card";
import { formatBytes, formatRelativeDate } from "@/utils";
import MemoryCardNameDialog from "@/v2/components/Player/MemoryCardNameDialog.vue";
import { useConfirm } from "@/v2/composables/useConfirm";
import { useSnackbar } from "@/v2/composables/useSnackbar";
import { errorMessage } from "@/v2/utils/errorMessage";

const props = defineProps<{
  emulator: string;
  platformId?: number | null;
}>();

const emit = defineEmits<{
  // Fired after any mutation so a host (e.g. the picker) can refresh.
  (e: "changed"): void;
}>();

const { t } = useI18n();
const snackbar = useSnackbar();
const confirm = useConfirm();

const cards = ref<MemoryCardSchema[]>([]);
const loading = ref(false);

async function load(emulator: string): Promise<void> {
  if (!emulator) return;
  loading.value = true;
  try {
    const { data } = await memoryCardApi.getMemoryCards({ emulator });
    cards.value = data;
  } catch (err) {
    console.warn("[memory-cards] Could not fetch cards:", err);
    cards.value = [];
  } finally {
    loading.value = false;
  }
}

watch(() => props.emulator, load, { immediate: true });

// ── Create ──────────────────────────────────────────────────────────
const showCreate = ref(false);
const creating = ref(false);

async function submitCreate(name: string): Promise<void> {
  if (creating.value) return;
  creating.value = true;
  try {
    const { data } = await memoryCardApi.createMemoryCard({
      name,
      emulator: props.emulator,
      platform_id: props.platformId ?? null,
    });
    cards.value = [data, ...cards.value];
    showCreate.value = false;
    emit("changed");
    snackbar.success(t("play.memory-card-created"), { icon: "mdi-check-bold" });
  } catch (err) {
    snackbar.error(
      `${t("play.memory-card-create-failed")}: ${errorMessage(err)}`,
      {
        icon: "mdi-close-circle",
      },
    );
  } finally {
    creating.value = false;
  }
}

// ── Rename ──────────────────────────────────────────────────────────
const renameTarget = ref<MemoryCardSchema | null>(null);
const renaming = ref(false);

async function submitRename(name: string): Promise<void> {
  const card = renameTarget.value;
  if (!card || renaming.value) return;
  renaming.value = true;
  try {
    const { data } = await memoryCardApi.renameMemoryCard({
      id: card.id,
      name,
    });
    cards.value = cards.value.map((c) => (c.id === data.id ? data : c));
    renameTarget.value = null;
    emit("changed");
    snackbar.success(t("play.memory-card-renamed"), { icon: "mdi-check-bold" });
  } catch (err) {
    snackbar.error(
      `${t("play.memory-card-rename-failed")}: ${errorMessage(err)}`,
      {
        icon: "mdi-close-circle",
      },
    );
  } finally {
    renaming.value = false;
  }
}

// ── Share (public toggle) ───────────────────────────────────────────
const sharing = reactive(new Set<number>());

async function toggleShare(
  card: MemoryCardSchema,
  next: boolean,
): Promise<void> {
  if (sharing.has(card.id)) return;
  sharing.add(card.id);
  try {
    const { data } = await memoryCardApi.setMemoryCardVisibility({
      id: card.id,
      isPublic: next,
    });
    cards.value = cards.value.map((c) => (c.id === data.id ? data : c));
    emit("changed");
  } catch (err) {
    snackbar.error(
      `${t("play.memory-card-share-failed")}: ${errorMessage(err)}`,
      {
        icon: "mdi-close-circle",
      },
    );
  } finally {
    sharing.delete(card.id);
  }
}

// ── Delete ──────────────────────────────────────────────────────────
const deleting = reactive(new Set<number>());

async function confirmDelete(card: MemoryCardSchema): Promise<void> {
  // The confirmation is awaited, so without this a second press stacks a
  // second dialog behind the first and deletes a card that is already gone.
  if (deleting.has(card.id)) return;
  deleting.add(card.id);
  const ok = await confirm({
    title: t("play.delete-memory-card"),
    body: t("play.delete-memory-card-body", { name: card.name }),
    confirmText: t("common.delete"),
    tone: "danger",
    requireTyped: card.name,
  });
  try {
    if (!ok) return;
    await memoryCardApi.deleteMemoryCards({ cards: [card] });
    cards.value = cards.value.filter((c) => c.id !== card.id);
    versions.delete(card.id);
    emit("changed");
    snackbar.success(t("play.memory-card-deleted"), {
      icon: "mdi-check-circle",
    });
  } catch (err) {
    snackbar.error(
      `${t("play.memory-card-delete-failed")}: ${errorMessage(err)}`,
      {
        icon: "mdi-close-circle",
      },
    );
  } finally {
    deleting.delete(card.id);
  }
}

// ── Version history (lazy per card) ─────────────────────────────────
type VersionState = "loading" | MemoryCardVersionSchema[];
const versions = reactive(new Map<number, VersionState>());
const expanded = reactive(new Set<number>());

function isExpanded(id: number): boolean {
  return expanded.has(id);
}

async function loadVersions(cardId: number): Promise<void> {
  versions.set(cardId, "loading");
  try {
    const { data } = await memoryCardApi.getMemoryCardVersions({ id: cardId });
    versions.set(cardId, data);
  } catch (err) {
    console.warn("[memory-cards] Could not fetch versions:", err);
    versions.set(cardId, []);
  }
}

async function toggleVersions(card: MemoryCardSchema): Promise<void> {
  if (expanded.has(card.id)) {
    expanded.delete(card.id);
    return;
  }
  expanded.add(card.id);
  if (versions.has(card.id)) return;
  await loadVersions(card.id);
}

function versionList(id: number): MemoryCardVersionSchema[] {
  const v = versions.get(id);
  return Array.isArray(v) ? v : [];
}
function versionsLoading(id: number): boolean {
  return versions.get(id) === "loading";
}

// ── Download / upload ───────────────────────────────────────────────
const downloading = reactive(new Set<number>());
const uploading = ref(false);
const uploadInput = ref<HTMLInputElement | null>(null);

function filenameFromResponse(disposition: unknown, fallback: string): string {
  const match = /filename="?([^";]+)"?/.exec(String(disposition ?? ""));
  return match ? match[1] : fallback;
}

async function downloadCard(card: MemoryCardSchema): Promise<void> {
  if (downloading.has(card.id)) return;
  downloading.add(card.id);
  try {
    const response = await memoryCardApi.downloadMemoryCard({ id: card.id });
    const url = URL.createObjectURL(response.data);
    const a = document.createElement("a");
    a.href = url;
    a.download = filenameFromResponse(
      response.headers["content-disposition"],
      `${card.name}.zip`,
    );
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  } catch (err) {
    // The body of a failed blob request is itself a blob, so the usual detail
    // extraction has nothing to read: go by status instead.
    const status = (err as { response?: { status?: number } })?.response
      ?.status;
    snackbar.error(
      status === 404
        ? t("play.memory-card-no-data")
        : t("play.memory-card-download-failed"),
      { icon: "mdi-close-circle" },
    );
  } finally {
    downloading.delete(card.id);
  }
}

function pickUpload(): void {
  const input = uploadInput.value;
  if (!input) return;
  // Clear first, so picking the same file twice still fires change.
  input.value = "";
  input.click();
}

async function onUploadPicked(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file || uploading.value) return;
  uploading.value = true;
  let created: MemoryCardSchema | null = null;
  try {
    const { data } = await memoryCardApi.createMemoryCard({
      name: file.name.replace(/\.zip$/i, "").trim() || t("play.memory-card"),
      emulator: props.emulator,
      platform_id: props.platformId ?? null,
    });
    created = data;
    await memoryCardApi.uploadMemoryCardVersion({ id: data.id, file });
    await load(props.emulator);
    emit("changed");
    snackbar.success(t("play.memory-card-uploaded"), {
      icon: "mdi-check-bold",
    });
  } catch (err) {
    // A card whose upload failed holds nothing, so drop it rather than leave
    // an empty card behind.
    if (created) {
      await memoryCardApi
        .deleteMemoryCards({ cards: [created] })
        .catch((cleanupErr) => {
          // The empty card survives; say so rather than reporting only the
          // upload failure and leaving it unexplained in the list.
          console.warn(
            "[memory-cards] Could not remove empty card:",
            cleanupErr,
          );
          void load(props.emulator);
        });
    }
    snackbar.error(
      `${t("play.memory-card-upload-failed")}: ${errorMessage(err)}`,
      {
        icon: "mdi-close-circle",
      },
    );
  } finally {
    uploading.value = false;
  }
}

const hasCards = computed(() => cards.value.length > 0);
</script>

<template>
  <div class="r-mc-mgr">
    <header v-if="hasCards" class="r-mc-mgr__head">
      <span class="r-mc-mgr__count">
        {{ t("play.memory-card-count", { count: cards.length }) }}
      </span>
      <RBtn
        variant="text"
        size="small"
        prepend-icon="mdi-upload"
        :disabled="uploading"
        @click="pickUpload"
      >
        {{ t("play.upload-memory-card") }}
      </RBtn>
      <RBtn
        variant="text"
        size="small"
        prepend-icon="mdi-plus"
        @click="showCreate = true"
      >
        {{ t("play.new-memory-card") }}
      </RBtn>
    </header>

    <ul v-if="hasCards" class="r-mc-mgr__list">
      <li v-for="card in cards" :key="card.id" class="r-mc-mgr__item">
        <div class="r-mc-mgr__row">
          <RIcon icon="mdi-sd" size="16" class="r-mc-mgr__row-icon" />
          <div class="r-mc-mgr__row-body">
            <div class="r-mc-mgr__row-name-line">
              <span class="r-mc-mgr__row-name">{{ card.name }}</span>
              <RChip
                v-if="card.is_public"
                size="x-small"
                variant="translucent"
                color="info"
                prepend-icon="mdi-account-group"
              >
                {{ t("play.memory-card-shared") }}
              </RChip>
            </div>
            <span class="r-mc-mgr__row-meta">
              {{
                t("play.memory-card-updated", {
                  when: formatRelativeDate(card.updated_at),
                })
              }}
            </span>
          </div>
          <div class="r-mc-mgr__row-actions">
            <RSwitch
              :model-value="card.is_public ?? false"
              :disabled="sharing.has(card.id)"
              hide-details
              :aria-label="t('play.memory-card-share-label')"
              :title="t('play.memory-card-share-label')"
              @update:model-value="(v) => toggleShare(card, v)"
            />
            <RBtn
              variant="text"
              size="small"
              icon="mdi-download"
              :disabled="downloading.has(card.id)"
              :aria-label="t('play.download-memory-card')"
              :title="t('play.download-memory-card')"
              @click="downloadCard(card)"
            />
            <RBtn
              variant="text"
              size="small"
              icon="mdi-history"
              :aria-label="t('play.memory-card-versions')"
              :title="t('play.memory-card-versions')"
              :class="{ 'r-mc-mgr__toggle--on': isExpanded(card.id) }"
              @click="toggleVersions(card)"
            />
            <RBtn
              variant="text"
              size="small"
              icon="mdi-pencil-outline"
              :aria-label="t('play.rename-memory-card')"
              :title="t('play.rename-memory-card')"
              @click="renameTarget = card"
            />
            <RBtn
              variant="text"
              size="small"
              icon="mdi-delete-outline"
              color="danger"
              :disabled="deleting.has(card.id)"
              :aria-label="t('play.delete-memory-card')"
              :title="t('play.delete-memory-card')"
              @click="confirmDelete(card)"
            />
          </div>
        </div>

        <!-- Version history (lazy) -->
        <div v-if="isExpanded(card.id)" class="r-mc-mgr__versions">
          <div v-if="versionsLoading(card.id)" class="r-mc-mgr__versions-empty">
            <RSpinner :size="14" />
            <span>{{ t("play.memory-card-versions") }}</span>
          </div>
          <p
            v-else-if="versionList(card.id).length === 0"
            class="r-mc-mgr__versions-empty"
          >
            {{ t("play.memory-card-no-versions") }}
          </p>
          <ul v-else class="r-mc-mgr__versions-list">
            <li
              v-for="v in versionList(card.id)"
              :key="v.id"
              class="r-mc-mgr__version"
              :class="{ 'r-mc-mgr__version--missing': v.missing_from_fs }"
            >
              <RIcon icon="mdi-content-save-outline" size="13" />
              <span class="r-mc-mgr__version-when">
                {{ formatRelativeDate(v.created_at) }}
              </span>
              <RChip size="x-small" variant="translucent">
                {{ formatBytes(v.file_size_bytes) }}
              </RChip>
              <span class="r-mc-mgr__version-spacer" />
              <a
                v-if="!v.missing_from_fs"
                :href="v.download_path"
                :download="v.file_name"
                class="r-mc-mgr__version-dl"
                :title="t('common.download')"
                :aria-label="t('common.download')"
              >
                <RIcon icon="mdi-download" size="14" />
              </a>
            </li>
          </ul>
        </div>
      </li>
    </ul>

    <REmptyState
      v-else-if="!loading"
      variant="boxed"
      icon="mdi-sd"
      :message="t('play.memory-cards-empty')"
    >
      <template #actions>
        <RBtn
          variant="flat"
          color="primary"
          prepend-icon="mdi-plus"
          @click="showCreate = true"
        >
          {{ t("play.new-memory-card") }}
        </RBtn>
        <RBtn
          variant="text"
          prepend-icon="mdi-upload"
          :disabled="uploading"
          @click="pickUpload"
        >
          {{ t("play.upload-memory-card") }}
        </RBtn>
      </template>
    </REmptyState>

    <input
      ref="uploadInput"
      type="file"
      accept=".zip,application/zip"
      class="r-mc-mgr__file"
      :aria-label="t('play.upload-memory-card')"
      @change="onUploadPicked"
    />

    <MemoryCardNameDialog
      v-model="showCreate"
      :title="t('play.create-memory-card')"
      :confirm-label="t('common.create')"
      confirm-icon="mdi-plus"
      :busy="creating"
      @submit="submitCreate"
    />

    <MemoryCardNameDialog
      :model-value="renameTarget !== null"
      icon="mdi-pencil-outline"
      :title="t('play.rename-memory-card')"
      :confirm-label="t('common.save')"
      :initial-name="renameTarget?.name ?? ''"
      :busy="renaming"
      @update:model-value="
        (v) => {
          if (!v) renameTarget = null;
        }
      "
      @submit="submitRename"
    />
  </div>
</template>

<style scoped>
.r-mc-mgr {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.r-mc-mgr__head {
  display: flex;
  align-items: center;
  gap: 8px;
}
.r-mc-mgr__count {
  margin-right: auto;
  font-size: var(--r-font-size-sm);
  font-weight: var(--r-font-weight-semibold);
  color: var(--r-color-fg-secondary);
}

.r-mc-mgr__list {
  list-style: none;
  margin: 0;
  padding: 0;
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-md);
  overflow: hidden;
  background: var(--r-color-bg-elevated);
}

.r-mc-mgr__item {
  border-bottom: 1px solid var(--r-color-border);
}
.r-mc-mgr__item:last-child {
  border-bottom: 0;
}

.r-mc-mgr__row {
  display: grid;
  grid-template-columns: auto 1fr auto;
  gap: 10px;
  align-items: center;
  padding: 10px 12px;
  transition: background var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-mc-mgr__row:hover {
  background: var(--r-color-surface-hover);
}

.r-mc-mgr__row-icon {
  color: var(--r-color-fg-muted);
}

.r-mc-mgr__row-body {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.r-mc-mgr__row-name-line {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}
.r-mc-mgr__row-name {
  font-size: 13px;
  font-weight: var(--r-font-weight-medium);
  color: var(--r-color-fg);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.r-mc-mgr__row-meta {
  font-size: var(--r-font-size-xs);
  color: var(--r-color-fg-muted);
}

.r-mc-mgr__row-actions {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  flex-shrink: 0;
}
.r-mc-mgr__toggle--on {
  color: var(--r-color-brand-primary);
}

.r-mc-mgr__file {
  display: none;
}

/* ── Versions ──────────────────────────────────────────────────── */
.r-mc-mgr__versions {
  padding: 4px 12px 10px 38px;
  background: var(--r-color-bg);
}
.r-mc-mgr__versions-empty {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 0;
  padding: 6px 0;
  font-size: var(--r-font-size-xs);
  color: var(--r-color-fg-muted);
}
.r-mc-mgr__versions-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.r-mc-mgr__version {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 0;
  font-size: var(--r-font-size-xs);
  color: var(--r-color-fg-secondary);
}
.r-mc-mgr__version--missing {
  color: var(--r-color-fg-muted);
  text-decoration: line-through;
}
.r-mc-mgr__version-when {
  font-weight: var(--r-font-weight-medium);
}
.r-mc-mgr__version-spacer {
  flex: 1 1 auto;
}
.r-mc-mgr__version-dl {
  display: inline-flex;
  align-items: center;
  color: var(--r-color-fg-secondary);
  transition: color var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-mc-mgr__version-dl:hover {
  color: var(--r-color-brand-primary);
}
</style>
