<template>
  <div class="multi-note-manager">
    <!-- Add New Note Button -->
    <div class="d-flex justify-space-between align-center mb-4">
      <v-btn
        :disabled="!scopes.includes('roms.user.write')"
        color="primary"
        prepend-icon="mdi-plus"
        @click="showAddNoteDialog = true"
      >
        {{ t("rom.add-note") }}
      </v-btn>
    </div>

    <!-- Current User Notes -->
    <div v-if="currentUserNotes.length > 0" class="mb-6">
      <h3 class="text-h6 mb-3">{{ t("rom.your-notes") }}</h3>
      <div
        v-for="note in currentUserNotes"
        :key="note.title"
        class="note-card mb-4"
      >
        <v-card variant="outlined">
          <v-card-title class="d-flex justify-space-between align-center">
            <span>{{ note.title }}</span>
            <div class="d-flex gap-2">
              <v-chip
                :color="note.is_public ? 'success' : 'warning'"
                size="small"
                variant="outlined"
              >
                {{ note.is_public ? t("rom.public") : t("rom.private") }}
              </v-chip>
              <v-btn
                :disabled="editingNotes[note.title]"
                icon="mdi-pencil"
                size="small"
                variant="text"
                @click="editNote(note.title)"
              />
              <v-btn
                :disabled="editingNotes[note.title]"
                color="error"
                icon="mdi-delete"
                size="small"
                variant="text"
                @click="confirmDeleteNote(note.title)"
              />
            </div>
          </v-card-title>
          <v-card-text>
            <MdPreview
              v-if="!editingNotes[note.title]"
              :model-value="note.content"
              :theme="theme.global.name.value === 'dark' ? 'dark' : 'light'"
            />
            <div v-else class="edit-container">
              <MdEditor
                v-model="editableNotes[note.title].content"
                :theme="theme.global.name.value === 'dark' ? 'dark' : 'light'"
                class="mb-3"
                language="en-US"
              />
              <v-switch
                v-model="editableNotes[note.title].is_public"
                :label="t('rom.make-public')"
                color="success"
                density="compact"
                hide-details
              />
              <div class="d-flex gap-2 mt-3">
                <v-btn
                  color="primary"
                  size="small"
                  @click="saveNote(note.title)"
                >
                  {{ t("common.save") }}
                </v-btn>
                <v-btn size="small" variant="outlined" @click="cancelAddNote()">
                  {{ t("common.cancel") }}
                </v-btn>
              </div>
            </div>
          </v-card-text>
          <v-card-subtitle v-if="note.updated_at" class="text-caption">
            {{ t("rom.last-updated") }}:
            {{ new Date(note.updated_at).toLocaleString() }}
          </v-card-subtitle>
        </v-card>
      </div>
    </div>

    <!-- Public Notes from Other Users -->
    <div v-if="otherUsersPublicNotes.length > 0" class="mb-6">
      <h3 class="text-h6 mb-3">{{ t("rom.community-notes") }}</h3>
      <div
        v-for="note in otherUsersPublicNotes"
        :key="`${note.user_id}-${note.title}`"
        class="note-card mb-4"
      >
        <v-card variant="outlined" class="community-note">
          <v-card-title class="d-flex justify-space-between align-center">
            <span>{{ note.title }}</span>
            <v-chip color="info" size="small" variant="outlined">
              {{ t("rom.by-user", { username: note.username }) }}
            </v-chip>
          </v-card-title>
          <v-card-text>
            <MdPreview
              :model-value="note.content"
              :theme="theme.global.name.value === 'dark' ? 'dark' : 'light'"
            />
          </v-card-text>
          <v-card-subtitle v-if="note.updated_at" class="text-caption">
            {{ t("rom.last-updated") }}:
            {{ new Date(note.updated_at).toLocaleString() }}
          </v-card-subtitle>
        </v-card>
      </div>
    </div>

    <!-- Empty State -->
    <div
      v-if="currentUserNotes.length === 0 && otherUsersPublicNotes.length === 0"
      class="text-center py-8"
    >
      <v-icon color="grey" size="64">mdi-note-text-outline</v-icon>
      <p class="text-h6 text-grey mt-4 mb-2">{{ t("rom.no-notes") }}</p>
      <p class="text-body-2 text-grey">{{ t("rom.no-notes-desc") }}</p>
    </div>

    <!-- Add Note Dialog -->
    <v-dialog v-model="showAddNoteDialog" max-width="500">
      <v-card>
        <v-card-title>{{ t("rom.add-new-note") }}</v-card-title>
        <v-card-text>
          <v-text-field
            v-model="newNoteTitle"
            :label="t('rom.note-title')"
            :error-messages="newNoteTitleErrors"
            variant="outlined"
            class="mb-3"
          />
          <v-switch
            v-model="newNoteIsPublic"
            :label="t('rom.make-public')"
            color="primary"
          />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn @click="cancelAddNote">{{ t("common.cancel") }}</v-btn>
          <v-btn
            color="primary"
            :disabled="!newNoteTitle.trim() || newNoteTitleErrors.length > 0"
            @click="addNewNote"
          >
            {{ t("common.add") }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Delete Confirmation Dialog -->
    <v-dialog v-model="showDeleteDialog" max-width="400">
      <v-card>
        <v-card-title>{{ t("common.confirm-deletion") }}</v-card-title>
        <v-card-text>
          {{ t("rom.confirm-delete-note", { title: noteToDelete }) }}
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn @click="showDeleteDialog = false">{{
            t("common.cancel")
          }}</v-btn>
          <v-btn color="error" @click="deleteNote">{{
            t("common.delete")
          }}</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </div>
</template>

<script setup lang="ts">
import { MdEditor, MdPreview } from "md-editor-v3";
import "md-editor-v3/lib/style.css";
import { storeToRefs } from "pinia";
import { computed, ref, reactive, watch } from "vue";
import { useI18n } from "vue-i18n";
import { useTheme } from "vuetify";
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
const newNoteIsPublic = ref(false);
const noteToDelete = ref("");
const editingNotes = reactive<Record<string, boolean>>({});
const editableNotes = reactive<
  Record<string, { content: string; is_public: boolean }>
>({});

// Computed
const currentUserNotes = computed(() => {
  // Get current user's notes from all_user_notes
  return (
    props.rom.all_user_notes?.filter(
      (note) => note.user_id === auth.user?.id,
    ) || []
  );
});

const otherUsersPublicNotes = computed(() => {
  // Get public notes from other users
  return (
    props.rom.all_user_notes?.filter(
      (note) => note.user_id !== auth.user?.id && note.is_public,
    ) || []
  );
});

const notesList = computed(() => {
  // Combine current user's notes with other users' public notes
  return [...currentUserNotes.value, ...otherUsersPublicNotes.value].sort(
    (a, b) =>
      new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime(),
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

// Methods
function formatDate(dateString: string): string {
  return new Date(dateString).toLocaleDateString();
}

function getCurrentUserNotesAsObject(): Record<string, any> {
  // Convert current user's notes from all_user_notes back to object format
  const notesObject: Record<string, any> = {};
  currentUserNotes.value.forEach((note: any) => {
    notesObject[note.title] = {
      content: note.content,
      is_public: note.is_public,
      created_at: note.created_at,
      updated_at: note.updated_at,
    };
  });
  return notesObject;
}

async function addNewNote() {
  if (!newNoteTitle.value.trim() || newNoteTitleErrors.value.length > 0) return;

  try {
    const currentUserNotesObject = getCurrentUserNotesAsObject();
    const updatedNotes = { ...currentUserNotesObject };
    updatedNotes[newNoteTitle.value.trim()] = {
      content: "",
      is_public: newNoteIsPublic.value,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };

    await romApi.updateUserRomProps({
      romId: props.rom.id,
      data: { notes: updatedNotes },
    });

    // Emit event to trigger ROM refetch (to get updated all_user_notes)
    emit("notesUpdated");
    cancelAddNote();
  } catch (error) {
    console.error("Failed to add note:", error);
  }
}

function cancelAddNote() {
  showAddNoteDialog.value = false;
  newNoteTitle.value = "";
  newNoteIsPublic.value = false;
}

function editNote(title: string) {
  if (editingNotes[title]) {
    // Save the note
    saveNote(title);
  } else {
    // Start editing
    const note = notesList.value.find((n) => n.title === title);
    if (note) {
      editableNotes[title] = {
        content: note.content,
        is_public: note.is_public,
      };
      editingNotes[title] = true;
    }
  }
}

async function saveNote(title: string) {
  try {
    const updatedNotes = { ...(props.rom.rom_user?.notes || {}) };
    if (updatedNotes[title]) {
      updatedNotes[title] = {
        ...updatedNotes[title],
        content: editableNotes[title].content,
        is_public: editableNotes[title].is_public,
        updated_at: new Date().toISOString(),
      };
    }

    await romApi.updateUserRomProps({
      romId: props.rom.id,
      data: { notes: updatedNotes },
    });

    editingNotes[title] = false;
    emit("notesUpdated");
  } catch (error) {
    console.error("Failed to save note:", error);
  }
}

async function toggleNoteVisibility(title: string) {
  try {
    const updatedNotes = { ...getCurrentUserNotesAsObject() };
    if (updatedNotes[title]) {
      updatedNotes[title] = {
        ...updatedNotes[title],
        is_public: !updatedNotes[title].is_public,
        updated_at: new Date().toISOString(),
      };
    }

    await romApi.updateUserRomProps({
      romId: props.rom.id,
      data: { notes: updatedNotes },
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
    const updatedNotes = { ...(props.rom.rom_user?.notes || {}) };
    delete updatedNotes[noteToDelete.value];

    await romApi.updateUserRomProps({
      romId: props.rom.id,
      data: { notes: updatedNotes },
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
  () => props.rom.rom_user?.notes,
  (newNotes) => {
    // Clean up editing states for notes that no longer exist
    Object.keys(editingNotes).forEach((title) => {
      if (!newNotes || !newNotes[title]) {
        delete editingNotes[title];
        delete editableNotes[title];
      }
    });
  },
  { deep: true },
);
</script>

<style scoped>
.multi-note-manager {
  width: 100%;
}

.v-expansion-panel-title {
  padding: 16px 20px;
}

.v-expansion-panel-text {
  border-top: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
}
</style>
