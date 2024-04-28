<script setup lang="ts">
import { ref } from "vue";
import { useTheme } from "vuetify";

import { type Rom } from "@/stores/roms";
import storeAuth from "@/stores/auth";
import { MdEditor, MdPreview } from "md-editor-v3";
import "md-editor-v3/lib/style.css";

const props = defineProps<{ rom: Rom }>();
const auth = storeAuth();
const theme = useTheme();

const ownNote = ref(
  props.rom.notes?.find((note) => note.user_id === auth.user?.id) ?? {
    id: null,
    user_id: auth.user?.id,
    rom_id: props.rom.id,
    last_edited_at: new Date(),
    raw_markdown: "",
    is_public: false,
  }
);
const publicNotes =
  props.rom.notes?.filter((note) => note.user_id !== auth.user?.id) ?? [];
const editingNote = ref(false);

const togglePublic = () => {
  ownNote.value.is_public = !ownNote.value.is_public;
};
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
          >
            <v-icon>
              {{ ownNote.is_public ? "mdi-eye" : "mdi-eye-off" }}
            </v-icon>
          </v-btn>
          <v-btn
            icon
            @click="editingNote = !editingNote"
            size="small"
            title="Edit note"
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
        theme="dark"
        language="en-US"
        :preview="false"
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
  <v-card v-if="publicNotes.length > 0">
    <v-card-title>
      <h3>Public notes</h3>
    </v-card-title>
    <v-card-text>
      <v-list>
        <v-list-item v-for="note in publicNotes" :key="note.id">
          <v-list-item-content>
            <v-list-item-title>{{ note.raw_markdown }}</v-list-item-title>
            <v-list-item-subtitle>{{
              note.user__username
            }}</v-list-item-subtitle>
          </v-list-item-content>
        </v-list-item>
      </v-list>
    </v-card-text>
  </v-card>
</template>
