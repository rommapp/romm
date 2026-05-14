<script setup lang="ts">
// NotesTab — per-ROM notes with a left index (own + community sections)
// and a right pane that swaps between MdPreview (read) and MdEditor
// (edit-in-place). Public/private toggles via a single icon button (no
// dialog), edits save inline, and the active note is URL-persistent via
// `?note=<id>` so links deep-link straight to a specific note.
import {
  REmptyState,
  RAvatar,
  RBtn,
  RIcon,
  RTextField,
  RTooltip,
  RDivider,
} from "@v2/lib";
import { MdEditor, MdPreview } from "md-editor-v3";
import "md-editor-v3/lib/style.css";
import { storeToRefs } from "pinia";
import { computed, nextTick, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import type { UserNoteSchema } from "@/__generated__";
import romApi from "@/services/api/rom";
import storeAuth from "@/stores/auth";
import type { DetailedRom } from "@/stores/roms";
import storeRoms from "@/stores/roms";
import { useConfirm } from "@/v2/composables/useConfirm";
import { useSnackbar } from "@/v2/composables/useSnackbar";
import { useThemeMode } from "@/v2/composables/useThemeMode";

defineOptions({ inheritAttrs: false });

const props = defineProps<{ rom: DetailedRom }>();

const snackbar = useSnackbar();
const confirm = useConfirm();
const authStore = storeAuth();
const romsStore = storeRoms();
const route = useRoute();
const router = useRouter();
const { isLight: isLightTheme } = useThemeMode();
const { user } = storeToRefs(authStore);

const mdTheme = computed<"light" | "dark">(() =>
  isLightTheme.value ? "light" : "dark",
);

const allNotes = computed<UserNoteSchema[]>(
  () => props.rom.all_user_notes ?? [],
);

function isOwn(note: UserNoteSchema): boolean {
  return user.value?.id != null && note.user_id === user.value.id;
}

const myNotes = computed<UserNoteSchema[]>(() =>
  allNotes.value
    .filter(isOwn)
    .slice()
    .sort((a, b) => a.title.localeCompare(b.title)),
);

const communityNotes = computed<UserNoteSchema[]>(() =>
  allNotes.value
    .filter((n) => !isOwn(n) && n.is_public)
    .slice()
    .sort((a, b) => a.title.localeCompare(b.title)),
);

const hasAnyNotes = computed(
  () => myNotes.value.length > 0 || communityNotes.value.length > 0,
);

const canCreate = computed(() => Boolean(user.value?.id));

// ── Selection (URL-synced via ?note=<id>) ────────────────────────
const selectedNoteId = ref<number | null>(null);

function readNoteFromQuery(): number | null {
  const v = route.query.note;
  if (typeof v !== "string") return null;
  const n = Number(v);
  if (!Number.isFinite(n)) return null;
  return allNotes.value.some((x) => x.id === n) ? n : null;
}

function writeNoteToQuery(id: number | null) {
  const next = { ...route.query };
  if (id === null) {
    delete next.note;
  } else {
    next.note = String(id);
  }
  if (route.query.note === next.note) return;
  router.replace({ path: route.path, query: next });
}

function defaultSelection(): number | null {
  if (myNotes.value.length > 0) return myNotes.value[0].id;
  if (communityNotes.value.length > 0) return communityNotes.value[0].id;
  return null;
}

selectedNoteId.value = readNoteFromQuery() ?? defaultSelection();

watch(selectedNoteId, (id) => writeNoteToQuery(id));

// React to URL changes (back/forward, external nav).
watch(
  () => route.query.note,
  () => {
    const fromQuery = readNoteFromQuery();
    if (fromQuery !== selectedNoteId.value) {
      selectedNoteId.value = fromQuery ?? defaultSelection();
    }
  },
);

// When the parent tab leaves Notes, drop ?note so the param doesn't
// leak across siblings (matches the SaveDataTab subtab pattern).
watch(
  () => route.query.tab,
  (value) => {
    if (value !== "notes" && route.query.note) {
      const next = { ...route.query };
      delete next.note;
      router.replace({ path: route.path, query: next });
    }
  },
);

const selectedNote = computed<UserNoteSchema | null>(() => {
  if (selectedNoteId.value === null) return null;
  return allNotes.value.find((n) => n.id === selectedNoteId.value) ?? null;
});

const isSelectedOwn = computed(() =>
  selectedNote.value ? isOwn(selectedNote.value) : false,
);

// ── Edit form ────────────────────────────────────────────────────
interface EditForm {
  id: number | null; // null when creating a new note
  title: string;
  content: string;
  isPublic: boolean;
}

const editForm = ref<EditForm | null>(null);
const saving = ref(false);
const togglingLockId = ref<number | null>(null);
// RTextField forwards $attrs to the underlying VTextField; we focus the
// inner <input> by reaching through .$el. Triggered when the form opens
// (user just clicked "Add" / "Edit"), so it's never a surprise focus.
const titleFieldRef = ref<{ $el?: HTMLElement } | null>(null);

watch(editForm, async (form) => {
  if (!form) return;
  await nextTick();
  titleFieldRef.value?.$el?.querySelector<HTMLInputElement>("input")?.focus();
});

const titleErrors = computed<string[]>(() => {
  const form = editForm.value;
  if (!form) return [];
  const trimmed = form.title.trim();
  if (!trimmed) return [];
  // Title must be unique across all visible notes (own + community),
  // matching v1's MultiNoteManager behaviour.
  const conflict = allNotes.value.some(
    (n) => n.title === trimmed && n.id !== form.id,
  );
  return conflict ? ["A note with this title already exists"] : [];
});

const canSave = computed(() => {
  const form = editForm.value;
  if (!form) return false;
  if (!form.title.trim()) return false;
  return titleErrors.value.length === 0;
});

async function refreshRom() {
  const { data } = await romApi.getRom({ romId: props.rom.id });
  romsStore.setCurrentRom(data);
}

function startAdd() {
  editForm.value = { id: null, title: "", content: "", isPublic: false };
}

function startEdit() {
  if (!selectedNote.value || !isSelectedOwn.value) return;
  editForm.value = {
    id: selectedNote.value.id,
    title: selectedNote.value.title,
    content: selectedNote.value.content,
    isPublic: selectedNote.value.is_public,
  };
}

function cancelEdit() {
  editForm.value = null;
}

async function saveEdit() {
  const form = editForm.value;
  if (!form || !canSave.value) return;
  saving.value = true;
  try {
    const payload = {
      title: form.title.trim(),
      content: form.content,
      is_public: form.isPublic,
    };
    if (form.id !== null) {
      await romApi.updateRomNote({
        romId: props.rom.id,
        noteId: form.id,
        noteData: payload,
      });
    } else {
      const { data } = await romApi.createRomNote({
        romId: props.rom.id,
        noteData: payload,
      });
      selectedNoteId.value = data.id;
    }
    await refreshRom();
    editForm.value = null;
    snackbar.success("Note saved", { icon: "mdi-check-circle" });
  } catch (err) {
    console.error("Note save failed:", err);
    snackbar.error("Could not save note", { icon: "mdi-close-circle" });
  } finally {
    saving.value = false;
  }
}

async function toggleLock(note: UserNoteSchema) {
  if (!isOwn(note)) return;
  togglingLockId.value = note.id;
  try {
    await romApi.updateRomNote({
      romId: props.rom.id,
      noteId: note.id,
      noteData: { is_public: !note.is_public },
    });
    await refreshRom();
  } catch (err) {
    console.error("Note visibility toggle failed:", err);
    snackbar.error("Could not change note visibility", {
      icon: "mdi-close-circle",
    });
  } finally {
    togglingLockId.value = null;
  }
}

async function removeNote(note: UserNoteSchema) {
  if (!isOwn(note)) return;
  const ok = await confirm({
    title: "Delete note?",
    body: `"${note.title}" will be permanently removed.`,
    confirmText: "Delete",
    tone: "danger",
  });
  if (!ok) return;
  try {
    await romApi.deleteRomNote({ romId: props.rom.id, noteId: note.id });
    if (selectedNoteId.value === note.id) {
      selectedNoteId.value = null;
    }
    await refreshRom();
    if (selectedNoteId.value === null) {
      selectedNoteId.value = defaultSelection();
    }
    snackbar.success("Note deleted", { icon: "mdi-check-circle" });
  } catch (err) {
    console.error("Note delete failed:", err);
    snackbar.error("Could not delete note", { icon: "mdi-close-circle" });
  }
}

function selectNote(id: number) {
  // Switching notes silently drops an unsaved draft — user picked a
  // different note, the intent is clear.
  if (editForm.value) editForm.value = null;
  selectedNoteId.value = id;
}

function fmtDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}
</script>

<template>
  <div class="r-v2-notes">
    <REmptyState
      v-if="!hasAnyNotes && !editForm"
      icon="mdi-note-text-outline"
      title="No notes yet"
      hint="Capture tips, walkthroughs or anything else worth remembering about this game."
    >
      <template v-if="canCreate" #actions>
        <RBtn
          variant="flat"
          color="primary"
          prepend-icon="mdi-plus"
          @click="startAdd"
        >
          Add your first note
        </RBtn>
      </template>
    </REmptyState>

    <div v-else class="r-v2-notes__body">
      <aside class="r-v2-notes__index">
        <template v-if="myNotes.length > 0">
          <div class="r-v2-notes__group-label">My notes</div>
          <ul class="r-v2-notes__group">
            <li v-for="n in myNotes" :key="n.id">
              <button
                type="button"
                class="r-v2-notes__nav-item"
                :class="{
                  'r-v2-notes__nav-item--active':
                    !editForm && selectedNoteId === n.id,
                }"
                @click="selectNote(n.id)"
              >
                <span class="r-v2-notes__nav-title">{{ n.title }}</span>
                <RIcon
                  v-if="!n.is_public"
                  icon="mdi-lock"
                  size="13"
                  class="r-v2-notes__nav-lock"
                />
              </button>
            </li>
          </ul>
        </template>
        <RBtn
          :disabled="!canCreate || !!editForm"
          variant="outlined"
          prepend-icon="mdi-plus"
          block
          class="r-v2-notes__add-btn"
          @click="startAdd"
        >
          Add note
        </RBtn>

        <template v-if="communityNotes.length > 0">
          <RDivider />
          <div class="r-v2-notes__group-label">Community</div>
          <ul class="r-v2-notes__group">
            <li v-for="n in communityNotes" :key="n.id">
              <button
                type="button"
                class="r-v2-notes__nav-item r-v2-notes__nav-item--rich"
                :class="{
                  'r-v2-notes__nav-item--active':
                    !editForm && selectedNoteId === n.id,
                }"
                @click="selectNote(n.id)"
              >
                <span class="r-v2-notes__nav-title">{{ n.title }}</span>
                <span class="r-v2-notes__nav-author">
                  <RAvatar icon="mdi-account" size="18" />
                  <span>{{ n.username }}</span>
                </span>
              </button>
            </li>
          </ul>
        </template>
      </aside>

      <section class="r-v2-notes__pane">
        <template v-if="editForm">
          <header class="r-v2-notes__pane-head">
            <RTextField
              ref="titleFieldRef"
              v-model="editForm.title"
              :error-messages="titleErrors"
              placeholder="Note title"
              hide-details="auto"
              density="compact"
              class="r-v2-notes__title-field"
              :disabled="saving"
            />
            <div class="r-v2-notes__actions">
              <RTooltip
                :text="editForm.isPublic ? 'Make private' : 'Make public'"
              >
                <template #activator="{ props: activator }">
                  <RBtn
                    v-bind="activator"
                    variant="text"
                    size="small"
                    :icon="
                      editForm.isPublic ? 'mdi-lock-open-variant' : 'mdi-lock'
                    "
                    :class="[
                      'r-v2-notes__lock-btn',
                      { 'r-v2-notes__lock-btn--locked': !editForm.isPublic },
                    ]"
                    :disabled="saving"
                    @click="editForm.isPublic = !editForm.isPublic"
                  />
                </template>
              </RTooltip>
              <RBtn
                variant="text"
                size="small"
                :disabled="saving"
                @click="cancelEdit"
              >
                Cancel
              </RBtn>
              <RBtn
                variant="flat"
                color="primary"
                size="small"
                prepend-icon="mdi-check"
                :loading="saving"
                :disabled="!canSave"
                @click="saveEdit"
              >
                Save
              </RBtn>
            </div>
          </header>
          <MdEditor
            v-model="editForm.content"
            no-highlight
            no-katex
            no-mermaid
            no-prettier
            no-upload-img
            :theme="mdTheme"
            language="en-US"
            :preview="false"
            class="r-v2-notes__editor"
          />
        </template>

        <template v-else-if="selectedNote">
          <header class="r-v2-notes__pane-head">
            <div class="r-v2-notes__pane-title-block">
              <h3 class="r-v2-notes__pane-title">
                {{ selectedNote.title }}
              </h3>
              <div v-if="!isSelectedOwn" class="r-v2-notes__author">
                <RAvatar icon="mdi-account" size="20" />
                <span>{{ selectedNote.username }}</span>
              </div>
            </div>
            <div v-if="isSelectedOwn" class="r-v2-notes__actions">
              <RTooltip
                :text="selectedNote.is_public ? 'Make private' : 'Make public'"
              >
                <template #activator="{ props: activator }">
                  <RBtn
                    v-bind="activator"
                    variant="text"
                    size="small"
                    :icon="
                      selectedNote.is_public
                        ? 'mdi-lock-open-variant'
                        : 'mdi-lock'
                    "
                    :class="[
                      'r-v2-notes__lock-btn',
                      {
                        'r-v2-notes__lock-btn--locked': !selectedNote.is_public,
                      },
                    ]"
                    :loading="togglingLockId === selectedNote.id"
                    @click="toggleLock(selectedNote)"
                  />
                </template>
              </RTooltip>
              <RTooltip text="Edit note">
                <template #activator="{ props: activator }">
                  <RBtn
                    v-bind="activator"
                    variant="text"
                    size="small"
                    icon="mdi-pencil-outline"
                    class="r-v2-notes__edit-btn"
                    @click="startEdit"
                  />
                </template>
              </RTooltip>
              <RTooltip text="Delete note">
                <template #activator="{ props: activator }">
                  <RBtn
                    v-bind="activator"
                    variant="text"
                    size="small"
                    color="romm-red"
                    icon="mdi-delete-outline"
                    @click="removeNote(selectedNote)"
                  />
                </template>
              </RTooltip>
            </div>
          </header>
          <MdPreview
            no-highlight
            no-katex
            no-mermaid
            :model-value="selectedNote.content"
            :theme="mdTheme"
            language="en-US"
            preview-theme="vuepress"
            code-theme="github"
            class="r-v2-notes__preview"
          />
          <footer class="r-v2-notes__pane-foot">
            Updated {{ fmtDate(selectedNote.updated_at) }}
          </footer>
        </template>

        <REmptyState
          v-else
          size="small"
          icon="mdi-note-search-outline"
          title="Pick a note from the list"
          hint="Or add a new one with the button above."
        />
      </section>
    </div>
  </div>
</template>

<style scoped>
.r-v2-notes {
  display: flex;
  flex-direction: column;
  gap: var(--r-space-3);
  min-height: 0;
}

.r-v2-notes__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--r-space-3);
}
.r-v2-notes__heading {
  font-size: var(--r-font-size-xl);
  font-weight: var(--r-font-weight-semibold);
  color: var(--r-color-fg);
  margin: 0;
}

/* Two-column body. Index left, content right. */
.r-v2-notes__body {
  display: grid;
  grid-template-columns: 240px 1fr;
  gap: var(--r-space-5);
  align-items: start;
  min-height: 0;
}

/* ── Index pane ── */
.r-v2-notes__index {
  display: flex;
  flex-direction: column;
  gap: var(--r-space-3);
  position: sticky;
  top: 0;
}
.r-v2-notes__add-btn {
  margin-bottom: var(--r-space-1);
}
.r-v2-notes__group-label {
  font-size: var(--r-font-size-xs);
  font-weight: var(--r-font-weight-bold);
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--r-color-fg-muted);
}
.r-v2-notes__group {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.r-v2-notes__nav-item {
  width: 100%;
  appearance: none;
  /* Subtle resting surface so each entry reads as a clickable card,
     not as plain text. Hover and active escalate from here. */
  background: var(--r-color-bg-elevated);
  border: none;
  cursor: pointer;
  text-align: left;
  padding: 8px 12px;
  border-radius: var(--r-radius-md);
  color: var(--r-color-fg-muted);
  font-family: inherit;
  font-size: var(--r-font-size-md);
  font-weight: var(--r-font-weight-medium);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--r-space-2);
  transition:
    background var(--r-motion-fast) var(--r-motion-ease-out),
    color var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-v2-notes__nav-item:not(.r-v2-notes__nav-item--active):hover {
  background: var(--r-color-surface-hover);
  color: var(--r-color-fg);
}
.r-v2-notes__nav-item--active {
  background: color-mix(in srgb, var(--r-color-brand-primary) 18%, transparent);
  color: var(--r-color-brand-primary);
}
.r-v2-notes__nav-item--rich {
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
  padding: 10px 12px;
}
.r-v2-notes__nav-title {
  flex: 1;
  min-width: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.r-v2-notes__nav-lock {
  color: var(--r-color-fg-faint);
  flex-shrink: 0;
}
.r-v2-notes__nav-author {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: var(--r-font-size-sm);
  font-weight: var(--r-font-weight-regular);
  color: var(--r-color-fg-faint);
}

/* ── Right pane ── */
.r-v2-notes__pane {
  display: flex;
  flex-direction: column;
  gap: var(--r-space-4);
  background: var(--r-color-bg-elevated);
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-card);
  padding: var(--r-space-5);
  min-width: 0;
}
.r-v2-notes__pane-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--r-space-3);
  min-width: 0;
}
.r-v2-notes__pane-title-block {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
  flex: 1;
}
.r-v2-notes__pane-title {
  margin: 0;
  font-size: var(--r-font-size-xl);
  font-weight: var(--r-font-weight-semibold);
  color: var(--r-color-fg);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.r-v2-notes__title-field {
  flex: 1;
  min-width: 0;
}
.r-v2-notes__author {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: var(--r-font-size-sm);
  color: var(--r-color-fg-muted);
}
.r-v2-notes__actions {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

/* Action-bar palette. Primary is reserved for primary actions (Add note,
   selected note in the index, locked indicator). Secondary actions get
   their own muted/distinct tones so the bar reads at a glance.
     · Lock — locked: brand-primary (private = personal/protected)
              unlocked: fg-muted (public = no special state)
     · Edit — overlay-fg (whitish, matches GameActionBtn — it's an action)
     · Delete — error (red, destructive — set on the activator above) */
.r-v2-notes__lock-btn :deep(.r-btn__content) {
  color: var(--r-color-fg-muted);
  transition: color var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-v2-notes__lock-btn--locked :deep(.r-btn__content) {
  color: var(--r-color-brand-primary);
}
.r-v2-notes__edit-btn :deep(.r-btn__content) {
  color: var(--r-color-overlay-fg);
}
.r-v2-notes__pane-foot {
  font-size: var(--r-font-size-sm);
  color: var(--r-color-fg-muted);
  /* No border / extra padding — the markdown surface above already
     provides the visual separation via its glass background. */
}

/* ── md-editor surface tweaks ──
   md-editor ships a white card by default. Both editor and preview share the same
   surface so the two modes feel like the same panel. */
.r-v2-notes__preview,
.r-v2-notes__editor {
  position: relative;
  background: color-mix(in srgb, black 28%, transparent);
  border-radius: var(--r-radius-lg);
  padding: 4px 18px;
}

.r-v2-notes__editor :deep(.md-editor) {
  --md-bk-color: transparent;
  --md-color: var(--r-color-fg);
  background: transparent;
  color: var(--r-color-fg);
  border: none;
  min-height: 320px;
  line-height: 1.5;
}
.r-v2-notes__editor :deep(.md-editor-toolbar-wrapper),
.r-v2-notes__editor :deep(.md-editor-content) {
  background: transparent;
  border: none;
}
.r-v2-notes__editor :deep(.md-editor-input-wrapper),
.r-v2-notes__editor :deep(textarea.md-editor-input) {
  background: transparent !important;
  color: var(--r-color-fg) !important;
}
.r-v2-notes__preview :deep(.md-editor),
.r-v2-notes__preview :deep(.md-editor-preview-wrapper) {
  background: transparent;
  color: var(--r-color-fg);
  padding: 0;
}
.r-v2-notes__preview :deep(.md-editor-preview),
.r-v2-notes__editor :deep(.md-editor-preview) {
  background: transparent !important;
  color: var(--r-color-fg);
  font-family: inherit;
  word-break: break-word;
  line-height: 1.55;
  padding: 0;
}
.r-v2-notes__preview :deep(.md-editor-preview blockquote),
.r-v2-notes__editor :deep(.md-editor-preview blockquote) {
  border-left-color: var(--r-color-border-strong);
}
.r-v2-notes__preview :deep(.md-editor-preview code),
.r-v2-notes__editor :deep(.md-editor-preview code),
.r-v2-notes__preview :deep(.md-editor-preview pre),
.r-v2-notes__editor :deep(.md-editor-preview pre) {
  background: color-mix(in srgb, black 30%, transparent) !important;
  color: var(--r-color-fg) !important;
}

/* Empty preview state — when md-preview gets no content it still renders
   an empty wrapper. Add a quiet hint line so the right pane isn't blank. */
.r-v2-notes__preview :deep(.md-editor-preview):empty::before {
  content: "(empty)";
  color: var(--r-color-fg-faint);
  font-style: italic;
}

@media (max-width: 768px) {
  .r-v2-notes__body {
    grid-template-columns: 1fr;
  }
  .r-v2-notes__index {
    position: static;
  }
}
</style>
