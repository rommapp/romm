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
import {
  RBtn,
  RChip,
  RDialog,
  REmptyState,
  RForm,
  RIcon,
  RSwitch,
  RTextField,
} from "@v2/lib";
import { computed, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import type {
  MemoryCardSchema,
  MemoryCardVersionSchema,
} from "@/__generated__";
import memoryCardApi from "@/services/api/memory-card";
import { formatBytes, formatRelativeDate } from "@/utils";
import { useConfirm } from "@/v2/composables/useConfirm";
import { useSnackbar } from "@/v2/composables/useSnackbar";
import { required } from "@/v2/utils/validation";

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

function errorText(err: unknown, fallbackKey: string): string {
  const e = err as {
    response?: { data?: { msg?: string; detail?: string } };
    message?: string;
  };
  return `${t(fallbackKey)}: ${
    e?.response?.data?.msg ||
    e?.response?.data?.detail ||
    e?.message ||
    t("common.unknown-error")
  }`;
}

const nameRules = [required(t("common.required"))];

// ── Create ──────────────────────────────────────────────────────────
const showCreate = ref(false);
const createName = ref("");
const creating = ref(false);
const createValid = ref(true);

function openCreate(): void {
  createName.value = "";
  showCreate.value = true;
}

async function submitCreate(): Promise<void> {
  const name = createName.value.trim();
  if (!name || creating.value) return;
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
    snackbar.error(errorText(err, "play.memory-card-create-failed"), {
      icon: "mdi-close-circle",
    });
  } finally {
    creating.value = false;
  }
}

// ── Rename ──────────────────────────────────────────────────────────
const renameTarget = ref<MemoryCardSchema | null>(null);
const renameName = ref("");
const renaming = ref(false);
const renameValid = ref(true);

function openRename(card: MemoryCardSchema): void {
  renameTarget.value = card;
  renameName.value = card.name;
}

async function submitRename(): Promise<void> {
  const card = renameTarget.value;
  const name = renameName.value.trim();
  if (!card || !name || renaming.value) return;
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
    snackbar.error(errorText(err, "play.memory-card-rename-failed"), {
      icon: "mdi-close-circle",
    });
  } finally {
    renaming.value = false;
  }
}

// ── Share (public toggle) ───────────────────────────────────────────
const sharing = ref<Set<number>>(new Set());

async function toggleShare(
  card: MemoryCardSchema,
  next: boolean,
): Promise<void> {
  if (sharing.value.has(card.id)) return;
  sharing.value = new Set(sharing.value).add(card.id);
  try {
    const { data } = await memoryCardApi.setMemoryCardVisibility({
      id: card.id,
      isPublic: next,
    });
    cards.value = cards.value.map((c) => (c.id === data.id ? data : c));
    emit("changed");
  } catch (err) {
    snackbar.error(errorText(err, "play.memory-card-share-failed"), {
      icon: "mdi-close-circle",
    });
  } finally {
    const s = new Set(sharing.value);
    s.delete(card.id);
    sharing.value = s;
  }
}

// ── Delete ──────────────────────────────────────────────────────────
async function confirmDelete(card: MemoryCardSchema): Promise<void> {
  const ok = await confirm({
    title: t("play.delete-memory-card"),
    body: t("play.delete-memory-card-body", { name: card.name }),
    confirmText: t("common.delete"),
    tone: "danger",
    requireTyped: card.name,
  });
  if (!ok) return;
  try {
    await memoryCardApi.deleteMemoryCards({ cards: [card] });
    cards.value = cards.value.filter((c) => c.id !== card.id);
    versions.value.delete(card.id);
    emit("changed");
    snackbar.success(t("play.memory-card-deleted"), {
      icon: "mdi-check-circle",
    });
  } catch (err) {
    snackbar.error(errorText(err, "play.memory-card-delete-failed"), {
      icon: "mdi-close-circle",
    });
  }
}

// ── Version history (lazy per card) ─────────────────────────────────
type VersionState = "loading" | MemoryCardVersionSchema[];
const versions = ref<Map<number, VersionState>>(new Map());
const expanded = ref<Set<number>>(new Set());

function isExpanded(id: number): boolean {
  return expanded.value.has(id);
}

async function toggleVersions(card: MemoryCardSchema): Promise<void> {
  const open = new Set(expanded.value);
  if (open.has(card.id)) {
    open.delete(card.id);
    expanded.value = open;
    return;
  }
  open.add(card.id);
  expanded.value = open;
  if (versions.value.has(card.id)) return;
  const next = new Map(versions.value);
  next.set(card.id, "loading");
  versions.value = next;
  try {
    const { data } = await memoryCardApi.getMemoryCardVersions({ id: card.id });
    const done = new Map(versions.value);
    done.set(card.id, data);
    versions.value = done;
  } catch (err) {
    console.warn("[memory-cards] Could not fetch versions:", err);
    const done = new Map(versions.value);
    done.set(card.id, []);
    versions.value = done;
  }
}

function versionList(id: number): MemoryCardVersionSchema[] {
  const v = versions.value.get(id);
  return Array.isArray(v) ? v : [];
}
function versionsLoading(id: number): boolean {
  return versions.value.get(id) === "loading";
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
        prepend-icon="mdi-plus"
        @click="openCreate"
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
              @click="openRename(card)"
            />
            <RBtn
              variant="text"
              size="small"
              icon="mdi-delete-outline"
              color="danger"
              :aria-label="t('play.delete-memory-card')"
              :title="t('play.delete-memory-card')"
              @click="confirmDelete(card)"
            />
          </div>
        </div>

        <!-- Version history (lazy) -->
        <div v-if="isExpanded(card.id)" class="r-mc-mgr__versions">
          <div v-if="versionsLoading(card.id)" class="r-mc-mgr__versions-empty">
            <RIcon icon="mdi-loading" size="14" class="r-mc-mgr__spin" />
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
          @click="openCreate"
        >
          {{ t("play.new-memory-card") }}
        </RBtn>
      </template>
    </REmptyState>

    <!-- Create dialog -->
    <RDialog
      v-model="showCreate"
      icon="mdi-sd"
      :width="420"
      @close="showCreate = false"
    >
      <template #header>
        <span>{{ t("play.create-memory-card") }}</span>
      </template>
      <template #content>
        <RForm v-model="createValid" @submit="submitCreate">
          <!-- eslint-disable vuejs-accessibility/no-autofocus -- autofocusing the first field on dialog open is intentional modal UX -->
          <RTextField
            v-model="createName"
            :placeholder="t('common.name')"
            prefix-label="stacked"
            :rules="nameRules"
            required
            autofocus
          >
            <template #prefix-label>
              {{ t("common.name") }}
            </template>
          </RTextField>
          <!-- eslint-enable vuejs-accessibility/no-autofocus -->
        </RForm>
      </template>
      <template #footer>
        <RBtn variant="text" :disabled="creating" @click="showCreate = false">
          {{ t("common.cancel") }}
        </RBtn>
        <RBtn
          variant="flat"
          color="primary"
          prepend-icon="mdi-plus"
          :disabled="!createName.trim() || creating"
          :loading="creating"
          @click="submitCreate"
        >
          {{ t("common.create") }}
        </RBtn>
      </template>
    </RDialog>

    <!-- Rename dialog -->
    <RDialog
      :model-value="renameTarget !== null"
      icon="mdi-pencil-outline"
      :width="420"
      @update:model-value="
        (v) => {
          if (!v) renameTarget = null;
        }
      "
      @close="renameTarget = null"
    >
      <template #header>
        <span>{{ t("play.rename-memory-card") }}</span>
      </template>
      <template #content>
        <RForm v-model="renameValid" @submit="submitRename">
          <!-- eslint-disable vuejs-accessibility/no-autofocus -- autofocusing the first field on dialog open is intentional modal UX -->
          <RTextField
            v-model="renameName"
            :placeholder="t('common.name')"
            prefix-label="stacked"
            :rules="nameRules"
            required
            autofocus
          >
            <template #prefix-label>
              {{ t("common.name") }}
            </template>
          </RTextField>
          <!-- eslint-enable vuejs-accessibility/no-autofocus -->
        </RForm>
      </template>
      <template #footer>
        <RBtn variant="text" :disabled="renaming" @click="renameTarget = null">
          {{ t("common.cancel") }}
        </RBtn>
        <RBtn
          variant="flat"
          color="primary"
          :disabled="!renameName.trim() || renaming"
          :loading="renaming"
          @click="submitRename"
        >
          {{ t("common.save") }}
        </RBtn>
      </template>
    </RDialog>
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
  justify-content: space-between;
  gap: 8px;
}
.r-mc-mgr__count {
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

.r-mc-mgr__spin {
  animation: r-mc-spin 1s linear infinite;
}
@keyframes r-mc-spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
