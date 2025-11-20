<script setup lang="ts">
import { MdEditor, MdPreview } from "md-editor-v3";
import "md-editor-v3/lib/style.css";
import { storeToRefs } from "pinia";
import { computed, ref, reactive, watch } from "vue";
import { useI18n } from "vue-i18n";
import { useTheme } from "vuetify";
import RDialog from "@/components/common/RDialog.vue";
import RSection from "@/components/common/RSection.vue";
import romApi from "@/services/api/rom";
import storeAuth from "@/stores/auth";
import type { DetailedRom } from "@/stores/roms";

const { t } = useI18n();
const theme = useTheme();
const auth = storeAuth();
const { scopes } = storeToRefs(auth);

const props = defineProps<{
  rom: DetailedRom;
}>();

const emit = defineEmits<{
  notesUpdated: [];
}>();

// State
const showAddNoteDialog = ref(false);
const showDeleteDialog = ref(false);
const newNoteTitle = ref("");
const newNoteContent = ref("");
const newNoteIsPublic = ref(false);
const noteToDelete = ref("");
const editingNotes = reactive<Record<string, boolean>>({});
const editableNotes = reactive<
  Record<string, { title: string; content: string; is_public: boolean }>
>({});
const expandedPanels = ref<string[]>([]);

// Computed
const currentUserNotes = computed(() => {
  // Get current user's notes from all_user_notes
  return (
    props.rom.all_user_notes
      ?.filter((note) => note.user_id === auth.user?.id)
      .sort((a, b) => a.title.localeCompare(b.title)) || []
  );
});

const otherUsersPublicNotes = computed(() => {
  // Get public notes from other users
  return (
    props.rom.all_user_notes
      ?.filter((note) => note.user_id !== auth.user?.id && note.is_public)
      .sort((a, b) => a.title.localeCompare(b.title)) || []
  );
});

const notesList = computed(() => {
  // Combine current user's notes with other users' public notes
  return [...currentUserNotes.value, ...otherUsersPublicNotes.value].sort(
    (a, b) => a.title.localeCompare(b.title),
  );
});

const newNoteTitleErrors = computed(() => {
  const errors: string[] = [];
  if (
    newNoteTitle.value.trim() &&
    notesList.value.some((note) => note.title === newNoteTitle.value.trim())
  ) {
    errors.push(t("rom.note-title-exists"));
  }
  return errors;
});

async function addNewNote() {
  if (!newNoteTitle.value.trim() || newNoteTitleErrors.value.length > 0) return;

  try {
    await romApi.createRomNote({
      romId: props.rom.id,
      noteData: {
        title: newNoteTitle.value.trim(),
        content: newNoteContent.value,
        is_public: newNoteIsPublic.value,
        tags: [],
      },
    });

    // Emit event to trigger ROM refetch
    emit("notesUpdated");
    closeAddNote();
  } catch (error) {
    console.error("Failed to add note:", error);
  }
}

function closeAddNote() {
  showAddNoteDialog.value = false;
  newNoteTitle.value = "";
  newNoteContent.value = "";
  newNoteIsPublic.value = false;
}

function toggleNewNoteVisibility() {
  newNoteIsPublic.value = !newNoteIsPublic.value;
}

function editNote(title: string) {
  if (editingNotes[title]) {
    // Save the note
    saveNote(title);
  } else {
    // Start editing
    const note = notesList.value.find((n) => n.title === title);
    if (note) {
      // Expand the panel if it's not already expanded
      if (!expandedPanels.value.includes(title)) {
        expandedPanels.value.push(title);
      }

      editableNotes[title] = {
        title: note.title,
        content: note.content,
        is_public: note.is_public,
      };
      editingNotes[title] = true;
    }
  }
}

async function saveNote(title: string) {
  try {
    const note = currentUserNotes.value.find((n) => n.title === title);
    if (!note) return;

    await romApi.updateRomNote({
      romId: props.rom.id,
      noteId: note.id,
      noteData: {
        title: editableNotes[title].title,
        content: editableNotes[title].content,
        is_public: editableNotes[title].is_public,
      },
    });

    editingNotes[title] = false;
    emit("notesUpdated");
  } catch (error) {
    console.error("Failed to save note:", error);
  }
}

async function toggleNoteVisibility(title: string) {
  try {
    const note = currentUserNotes.value.find((n) => n.title === title);
    if (!note) return;

    await romApi.updateRomNote({
      romId: props.rom.id,
      noteId: note.id,
      noteData: {
        is_public: !note.is_public,
      },
    });

    emit("notesUpdated");
  } catch (error) {
    console.error("Failed to toggle note visibility:", error);
  }
}

function confirmDeleteNote(title: string) {
  noteToDelete.value = title;
  showDeleteDialog.value = true;
}

async function deleteNote() {
  try {
    const note = currentUserNotes.value.find(
      (n) => n.title === noteToDelete.value,
    );
    if (!note) return;

    await romApi.deleteRomNote({
      romId: props.rom.id,
      noteId: note.id,
    });

    emit("notesUpdated");
    showDeleteDialog.value = false;

    // Clean up editing state
    delete editingNotes[noteToDelete.value];
    delete editableNotes[noteToDelete.value];
  } catch (error) {
    console.error("Failed to delete note:", error);
  }
}

// Watch for prop changes to update local state
watch(
  () => props.rom.all_user_notes,
  (newNotes) => {
    // Clean up editing states for notes that no longer exist
    const currentTitles = new Set(currentUserNotes.value.map((n) => n.title));
    Object.keys(editingNotes).forEach((title) => {
      if (!currentTitles.has(title)) {
        delete editingNotes[title];
        delete editableNotes[title];
      }
    });
  },
  { deep: true },
);
</script>

<template>
  <div class="multi-note-manager">
    <!-- Current User Notes Section -->
    <RSection
      icon="mdi-account"
      :title="t('rom.my-notes')"
      elevation="0"
      title-divider
      bg-color="bg-surface"
      class="mt-2"
    >
      <template #toolbar-append>
        <v-btn
          :disabled="!scopes.includes('roms.user.write')"
          color="primary"
          variant="outlined"
          prepend-icon="mdi-plus"
          class="bg-toplayer"
          @click="showAddNoteDialog = true"
        >
          {{ t("rom.add-note") }}
        </v-btn>
      </template>
      <template #content>
        <div v-if="currentUserNotes.length > 0">
          <v-expansion-panels
            v-model="expandedPanels"
            multiple
            flat
            variant="accordion"
          >
            <v-expansion-panel
              v-for="note in currentUserNotes"
              :key="note.title"
              :value="note.title"
              rounded="0"
            >
              <v-expansion-panel-title class="bg-toplayer">
                <div class="d-flex justify-space-between align-center w-100">
                  <v-text-field
                    v-if="editingNotes[note.title]"
                    v-model="editableNotes[note.title].title"
                    variant="outlined"
                    density="compact"
                    hide-details
                    class="mr-4"
                    @click.stop
                  />
                  <span v-else class="text-body-1">{{ note.title }}</span>
                  <div class="d-flex gap-2 align-center mr-4">
                    <v-tooltip
                      location="top"
                      class="tooltip"
                      transition="fade-transition"
                      :text="note.is_public ? 'Make private' : 'Make public'"
                      open-delay="500"
                    >
                      <template #activator="{ props: tooltipProps }">
                        <v-btn
                          :disabled="
                            !scopes.includes('roms.user.write') ||
                            editingNotes[note.title]
                          "
                          v-bind="tooltipProps"
                          :color="note.is_public ? 'romm-green' : 'accent'"
                          variant="outlined"
                          class="mr-2"
                          @click.stop="toggleNoteVisibility(note.title)"
                        >
                          <v-icon class="mr-2">
                            {{
                              note.is_public
                                ? "mdi-lock-open-variant"
                                : "mdi-lock"
                            }}
                          </v-icon>
                          {{
                            note.is_public ? t("rom.public") : t("rom.private")
                          }}
                        </v-btn>
                      </template>
                    </v-tooltip>
                    <v-btn-group divided density="compact">
                      <v-tooltip
                        location="top"
                        class="tooltip"
                        transition="fade-transition"
                        text="Edit note"
                        open-delay="500"
                      >
                        <template #activator="{ props: tooltipProps }">
                          <v-btn
                            :disabled="!scopes.includes('roms.user.write')"
                            v-bind="tooltipProps"
                            class="bg-toplayer"
                            @click.stop="editNote(note.title)"
                          >
                            <v-icon size="large">
                              {{
                                editingNotes[note.title]
                                  ? "mdi-check"
                                  : "mdi-pencil"
                              }}
                            </v-icon>
                          </v-btn>
                        </template>
                      </v-tooltip>
                      <v-tooltip
                        location="top"
                        class="tooltip"
                        transition="fade-transition"
                        text="Delete note"
                        open-delay="500"
                      >
                        <template #activator="{ props: tooltipProps }">
                          <v-btn
                            :disabled="
                              !scopes.includes('roms.user.write') ||
                              editingNotes[note.title]
                            "
                            v-bind="tooltipProps"
                            class="bg-toplayer"
                            @click.stop="confirmDeleteNote(note.title)"
                          >
                            <v-icon size="large" color="error"
                              >mdi-delete</v-icon
                            >
                          </v-btn>
                        </template>
                      </v-tooltip>
                    </v-btn-group>
                  </div>
                </div>
              </v-expansion-panel-title>
              <v-expansion-panel-text class="bg-surface">
                <MdEditor
                  v-if="editingNotes[note.title]"
                  v-model="editableNotes[note.title].content"
                  no-highlight
                  no-katex
                  no-mermaid
                  no-prettier
                  no-upload-img
                  :disabled="!scopes.includes('roms.user.write')"
                  :theme="theme.global.name.value === 'dark' ? 'dark' : 'light'"
                  language="en-US"
                  :preview="false"
                />
                <MdPreview
                  v-else
                  no-highlight
                  no-katex
                  no-mermaid
                  :model-value="note.content"
                  :theme="theme.global.name.value === 'dark' ? 'dark' : 'light'"
                  language="en-US"
                  preview-theme="vuepress"
                  code-theme="github"
                  class="py-4 px-6"
                />
                <v-card-subtitle
                  v-if="note.updated_at"
                  class="text-caption mt-2 mb-2"
                >
                  {{ t("common.last-updated") }}:
                  {{ new Date(note.updated_at).toLocaleString() }}
                </v-card-subtitle>
              </v-expansion-panel-text>
            </v-expansion-panel>
          </v-expansion-panels>
        </div>
        <div v-else class="text-center py-8">
          <v-icon color="grey" size="64">mdi-note-text-outline</v-icon>
          <p class="text-h6 text-grey mt-4 mb-2">{{ t("rom.no-notes") }}</p>
          <p class="text-body-2 text-grey">{{ t("rom.no-notes-desc") }}</p>
        </div>
      </template>
    </RSection>

    <!-- Public Notes from Other Users Section -->
    <RSection
      v-if="otherUsersPublicNotes.length > 0"
      icon="mdi-account-group"
      :title="t('rom.community-notes')"
      elevation="0"
      title-divider
      bg-color="bg-surface"
      class="mt-2"
    >
      <template #content>
        <v-expansion-panels multiple flat variant="accordion">
          <v-expansion-panel
            v-for="note in otherUsersPublicNotes"
            :key="`${note.user_id}-${note.title}`"
            rounded="0"
          >
            <v-expansion-panel-title class="bg-toplayer">
              <div class="d-flex justify-space-between align-center w-100">
                <span class="text-body-1">{{ note.title }}</span>
                <v-chip
                  color="info"
                  size="small"
                  variant="outlined"
                  class="mr-4"
                >
                  {{ note.username }}
                </v-chip>
              </div>
            </v-expansion-panel-title>
            <v-expansion-panel-text class="bg-surface">
              <MdPreview
                no-highlight
                no-katex
                no-mermaid
                :model-value="note.content"
                :theme="theme.global.name.value === 'dark' ? 'dark' : 'light'"
                language="en-US"
                preview-theme="vuepress"
                code-theme="github"
                class="py-4 px-6"
              />
              <v-card-subtitle
                v-if="note.updated_at"
                class="text-caption mt-2 mb-2"
              >
                {{ t("common.last-updated") }}:
                {{ new Date(note.updated_at).toLocaleString() }}
              </v-card-subtitle>
            </v-expansion-panel-text>
          </v-expansion-panel>
        </v-expansion-panels>
      </template>
    </RSection>

    <!-- Add Note Dialog -->
    <RDialog
      v-model="showAddNoteDialog"
      icon="mdi-note-plus"
      width="800"
      @close="closeAddNote"
    >
      <template #header>
        <v-toolbar-title>{{ t("rom.add-new-note") }}</v-toolbar-title>
      </template>
      <template #content>
        <div class="pa-4">
          <v-text-field
            v-model="newNoteTitle"
            :label="t('rom.note-title')"
            :error-messages="newNoteTitleErrors"
            variant="outlined"
            class="mb-3"
          />
          <v-card flat class="mb-3">
            <v-card-subtitle class="px-0 pb-2">{{
              t("rom.note-content")
            }}</v-card-subtitle>
            <MdEditor
              v-model="newNoteContent"
              no-highlight
              no-katex
              no-mermaid
              no-prettier
              no-upload-img
              :theme="theme.global.name.value === 'dark' ? 'dark' : 'light'"
              language="en-US"
              :preview="false"
              style="min-height: 200px"
            />
          </v-card>
          <v-btn
            :color="newNoteIsPublic ? 'romm-green' : 'accent'"
            variant="outlined"
            @click="toggleNewNoteVisibility"
          >
            <v-icon class="mr-2">
              {{ newNoteIsPublic ? "mdi-lock-open-variant" : "mdi-lock" }}
            </v-icon>
            {{ newNoteIsPublic ? t("rom.public") : t("rom.private") }}
          </v-btn>
        </div>
      </template>
      <template #footer>
        <v-spacer />
        <v-btn @click="closeAddNote">{{ t("common.cancel") }}</v-btn>
        <v-btn
          color="primary"
          :disabled="!newNoteTitle.trim() || newNoteTitleErrors.length > 0"
          @click="addNewNote"
        >
          {{ t("common.add") }}
        </v-btn>
      </template>
    </RDialog>

    <!-- Delete Confirmation Dialog -->
    <RDialog
      v-model="showDeleteDialog"
      icon="mdi-delete"
      width="400"
      @close="showDeleteDialog = false"
    >
      <template #header>
        <v-toolbar-title>{{ t("common.confirm-deletion") }}</v-toolbar-title>
      </template>
      <template #content>
        <div class="pa-4">
          {{ t("rom.confirm-delete-note", { title: noteToDelete }) }}
        </div>
      </template>
      <template #footer>
        <v-spacer />
        <v-btn @click="showDeleteDialog = false">{{
          t("common.cancel")
        }}</v-btn>
        <v-btn color="error" @click="deleteNote">{{
          t("common.delete")
        }}</v-btn>
      </template>
    </RDialog>
  </div>
</template>

<style scoped>
.multi-note-manager {
  width: 100%;
}

.md-editor-dark {
  --md-bk-color: #161b22 !important;
}

.md-editor,
.md-preview {
  line-height: 1.25 !important;
}

.md-editor-preview {
  word-break: break-word !important;
}

.md-editor-preview blockquote {
  border-left-color: rgba(var(--v-theme-secondary));
}

.md-editor-preview .md-editor-code-flag {
  visibility: hidden;
}

.md-editor-preview .md-editor-admonition {
  border-color: rgba(var(--v-theme-secondary));
  background-color: rgba(var(--v-theme-toplayer)) !important;
}

.md-editor-preview .md-editor-code summary,
.md-editor-preview .md-editor-code code {
  background-color: rgba(var(--v-theme-toplayer)) !important;
}

.vuepress-theme pre code {
  background-color: #0d1117;
}

.v-expansion-panel-text__wrapper {
  padding: 0px !important;
}
</style>
