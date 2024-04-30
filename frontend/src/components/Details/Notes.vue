<script setup lang="ts">
import { ref } from "vue";
import { useTheme } from "vuetify";

import { type Rom } from "@/stores/roms";
import storeAuth from "@/stores/auth";
import romApi from "@/services/api/rom";
import { MdEditor, MdPreview } from "md-editor-v3";
import "md-editor-v3/lib/style.css";

const props = defineProps<{ rom: Rom }>();
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
      <v-row>
        <v-col cols="10">
          <h3>My notes</h3>
        </v-col>
        <v-col cols="2" class="text-right">
          <v-btn
            icon
            @click="togglePublic"
            size="small"
            :title="ownNote.is_public ? 'Make private' : 'Make public'"
            class="mr-2"
          >
            <v-icon>
              {{ ownNote.is_public ? "mdi-eye" : "mdi-eye-off" }}
            </v-icon>
          </v-btn>
          <v-btn icon @click="onEditNote" size="small" title="Edit note">
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
        theme="dark"
        language="en-US"
        :preview="false"
        class="editor-preview"
      />
      <MdPreview
        v-else
        :modelValue="ownNote.raw_markdown"
        theme="dark"
        previewTheme="default"
        codeTheme="atom"
      />
    </v-card-text>
  </v-card>
  <v-card v-if="publicNotes.length > 0" class="mt-3">
    <v-card-title>
      <h3>Public notes</h3>
    </v-card-title>
    <v-card-text>
      <v-list>
        <v-list-item v-for="note in publicNotes" :key="note.id">
          <v-list-item-content>
            <v-list-item-title>{{
              note.user__username
            }}</v-list-item-title>
            <MdPreview
              :modelValue="note.raw_markdown"
              theme="dark"
              previewTheme="default"
              codeTheme="atom"
            />
          </v-list-item-content>
        </v-list-item>
      </v-list>
    </v-card-text>
  </v-card>
</template>

<style>
.md-editor-dark {
  --md-bk-color: #161b22 !important;
}
.md-editor h1,
.md-editor h2,
.md-editor h3,
.md-editor h4,
.md-editor h5,
.md-editor h6 {
  word-break: break-word !important;
}
.md-editor {
  line-height: 1.25 !important;
}
</style>
