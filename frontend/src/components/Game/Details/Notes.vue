<script setup lang="ts">
import romApi from "@/services/api/rom";
import storeAuth from "@/stores/auth";
import type { DetailedRom } from "@/stores/roms";
import { MdEditor, MdPreview } from "md-editor-v3";
import "md-editor-v3/lib/style.css";
import { ref } from "vue";
import { useTheme } from "vuetify";

const props = defineProps<{ rom: DetailedRom }>();
const auth = storeAuth();
const theme = useTheme();
const editingNote = ref(false);
const ownNote = ref(
  props.rom.user_notes?.find((note) => note.user_id === auth.user?.id) ?? {
    id: null,
    user_id: auth.user?.id,
    rom_id: props.rom.id,
    last_edited_at: new Date(),
    raw_markdown: "",
    is_public: false,
  }
);
const publicNotes =
  props.rom.user_notes?.filter((note) => note.user_id !== auth.user?.id) ?? [];

function togglePublic() {
  ownNote.value.is_public = !ownNote.value.is_public;
  romApi.updateRomNote({
    romId: props.rom.id,
    rawMarkdown: ownNote.value.raw_markdown,
    isPublic: ownNote.value.is_public,
  });
}

function onEditNote() {
  if (editingNote.value) {
    romApi.updateRomNote({
      romId: props.rom.id,
      rawMarkdown: ownNote.value.raw_markdown,
      isPublic: ownNote.value.is_public,
    });
  }
  editingNote.value = !editingNote.value;
}
</script>
<template>
  <v-card>
    <v-card-title>
      <v-row class="px-2 pt-1">
        <v-col
          cols="10"
          class="d-flex align-center"
        >
          <h3>My notes</h3>
        </v-col>
        <v-col
          cols="2"
          class="text-right"
        >
          <v-btn
            icon
            size="small"
            :title="ownNote.is_public ? 'Make private' : 'Make public'"
            class="mr-2"
            @click="togglePublic"
          >
            <v-icon>
              {{ ownNote.is_public ? "mdi-eye" : "mdi-eye-off" }}
            </v-icon>
          </v-btn>
          <v-btn
            icon
            size="small"
            title="Edit note"
            @click="onEditNote"
          >
            <v-icon>
              {{ editingNote ? "mdi-check" : "mdi-pencil" }}
            </v-icon>
          </v-btn>
        </v-col>
      </v-row>
    </v-card-title>
    <v-card-text>
      <MdEditor
        v-if="editingNote"
        v-model="ownNote.raw_markdown"
        :theme="theme.name.value == 'dark' ? 'dark' : 'light'"
        language="en-US"
        :preview="false"
        :no-upload-img="true"
        class="editor-preview"
      />
      <MdPreview
        v-else
        :model-value="ownNote.raw_markdown"
        :theme="theme.name.value == 'dark' ? 'dark' : 'light'"
        preview-theme="vuepress"
        code-theme="github"
      />
    </v-card-text>
  </v-card>
  <v-card
    v-if="publicNotes.length > 0"
    class="mt-3"
  >
    <v-card-title class="px-6 pt-4">
      <h3>Public notes</h3>
    </v-card-title>
    <v-card-text>
      <v-list>
        <v-list-item
          v-for="note in publicNotes"
          :key="note.id"
        >
          <v-list-item-title>{{ note.user__username }}</v-list-item-title>
          <MdPreview
            :model-value="note.raw_markdown"
            :theme="theme.name.value == 'dark' ? 'dark' : 'light'"
            preview-theme="vuepress"
            code-theme="github"
          />
        </v-list-item>
      </v-list>
    </v-card-text>
  </v-card>
</template>

<style>
.md-editor-dark {
  --md-bk-color: #161b22 !important;
}
.md-editor,
.md-editor-preview {
  word-break: break-word !important;
  line-height: 1.25 !important;
}
.vuepress-theme pre code {
  background-color: #0d1117;
}
</style>
