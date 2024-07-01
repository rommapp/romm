<script setup lang="ts">
import romApi from "@/services/api/rom";
import storeAuth from "@/stores/auth";
import type { DetailedRom } from "@/stores/roms";
import { MdEditor, MdPreview } from "md-editor-v3";
import "md-editor-v3/lib/style.css";
import { ref, watch } from "vue";
import { useTheme } from "vuetify";

// Props
const props = defineProps<{ rom: DetailedRom }>();
const auth = storeAuth();
const theme = useTheme();
const editingNote = ref(false);
const romUser = ref(
  props.rom.rom_user ?? {
    id: null,
    user_id: auth.user?.id,
    rom_id: props.rom.id,
    updated_at: new Date(),
    note_raw_markdown: "",
    note_is_public: false,
    is_main_sibling: false,
  }
);
const publicNotes =
  props.rom.user_notes?.filter((note) => note.user_id !== auth.user?.id) ?? [];

// Functions
function togglePublic() {
  romUser.value.note_is_public = !romUser.value.note_is_public;
  romApi.updateUserRomProps({
    romId: props.rom.id,
    noteRawMarkdown: romUser.value.note_raw_markdown,
    noteIsPublic: romUser.value.note_is_public,
    isMainSibling: romUser.value.is_main_sibling,
  });
}

function editNote() {
  if (editingNote.value) {
    romApi.updateUserRomProps({
      romId: props.rom.id,
      noteRawMarkdown: romUser.value.note_raw_markdown,
      noteIsPublic: romUser.value.note_is_public,
      isMainSibling: romUser.value.is_main_sibling,
    });
  }
  editingNote.value = !editingNote.value;
}

watch(
  () => props.rom,
  async () => {
    romUser.value = props.rom.rom_user ?? {
      id: null,
      user_id: auth.user?.id,
      rom_id: props.rom.id,
      updated_at: new Date(),
      note_raw_markdown: "",
      note_is_public: false,
      is_main_sibling: false,
    };
  }
);
</script>
<template>
  <v-card rounded="0">
    <v-card-title class="bg-terciary">
      <v-list-item class="pl-2 pr-0">
        <span class="text-h6">My notes</span>
        <template #append>
          <v-btn-group divided density="compact">
            <v-tooltip
              location="top"
              class="tooltip"
              transition="fade-transition"
              :text="romUser.note_is_public ? 'Make private' : 'Make public'"
              open-delay="500"
              ><template #activator="{ props: tooltipProps }">
                <v-btn
                  @click="togglePublic"
                  v-bind="tooltipProps"
                  class="bg-terciary"
                >
                  <v-icon size="large">
                    {{ romUser.note_is_public ? "mdi-eye" : "mdi-eye-off" }}
                  </v-icon>
                </v-btn>
              </template></v-tooltip
            >
            <v-tooltip
              location="top"
              class="tooltip"
              transition="fade-transition"
              text="Edit note"
              open-delay="500"
              ><template #activator="{ props: tooltipProps }">
                <v-btn
                  @click="editNote"
                  v-bind="tooltipProps"
                  class="bg-terciary"
                >
                  <v-icon size="large">
                    {{ editingNote ? "mdi-check" : "mdi-pencil" }}
                  </v-icon>
                </v-btn>
              </template></v-tooltip
            >
          </v-btn-group>
        </template>
      </v-list-item>
    </v-card-title>
    <v-card-text class="pa-2">
      <MdEditor
        v-if="editingNote"
        v-model="romUser.note_raw_markdown"
        :theme="theme.name.value == 'dark' ? 'dark' : 'light'"
        language="en-US"
        :preview="false"
        :no-upload-img="true"
        class="editor-preview"
      />
      <MdPreview
        v-else
        :model-value="romUser.note_raw_markdown"
        :theme="theme.name.value == 'dark' ? 'dark' : 'light'"
        preview-theme="vuepress"
        code-theme="github"
      />
    </v-card-text>
  </v-card>

  <v-card
    rounded="0"
    v-if="publicNotes && publicNotes.length > 0"
    class="mt-2"
  >
    <v-card-title class="bg-terciary">
      <v-list-item class="pl-2 pr-0">
        <span class="text-h6">Public notes</span>
      </v-list-item>
    </v-card-title>

    <v-divider />

    <v-card-text class="pa-0">
      <v-expansion-panels multiple flat rounded="0" variant="accordion">
        <v-expansion-panel v-for="note in publicNotes">
          <v-expansion-panel-title class="bg-terciary">
            <span class="text-body-1">{{ note.username }}</span>
          </v-expansion-panel-title>
          <v-expansion-panel-text class="bg-secondary">
            <MdPreview
              :model-value="note.note_raw_markdown"
              :theme="theme.name.value == 'dark' ? 'dark' : 'light'"
              preview-theme="vuepress"
              code-theme="github"
            />
          </v-expansion-panel-text>
        </v-expansion-panel>
      </v-expansion-panels>
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
.v-expansion-panel-text__wrapper {
  padding: 0px !important;
}
</style>
