<script setup lang="ts">
import { MdPreview } from "md-editor-v3";
import "md-editor-v3/lib/style.css";
import type { Emitter } from "mitt";
import { inject, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useTheme } from "vuetify";
import type { SimpleRom } from "@/stores/roms";
import type { Events } from "@/types/emitter";

const theme = useTheme();
const emitter = inject<Emitter<Events>>("emitter");
const { t } = useI18n();

const rom = ref<SimpleRom | null>(null);
const show = ref(false);

emitter?.on("showNoteDialog", (romToShow) => {
  rom.value = romToShow;
  show.value = true;
});
</script>

<template>
  <v-dialog v-model="show" max-width="600">
    <v-card>
      <v-card-title class="d-flex align-center">
        <v-icon class="mr-2"> mdi-notebook </v-icon>
        {{ t("rom.my-notes") }} - {{ rom?.name }}
        <v-spacer />
        <v-btn icon @click="show = false">
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-card-title>
      <v-card-text class="pa-4">
        <div
          v-if="
            rom?.rom_user?.notes && Object.keys(rom.rom_user.notes).length > 0
          "
        >
          <div
            v-for="(note, title) in rom.rom_user.notes"
            :key="title"
            class="mb-4"
          >
            <h4 class="text-h6 mb-2">{{ title }}</h4>
            <MdPreview
              no-highlight
              no-katex
              no-mermaid
              :model-value="note.content"
              :theme="theme.name.value == 'dark' ? 'dark' : 'light'"
              language="en-US"
              preview-theme="vuepress"
              code-theme="github"
              class="py-2"
            />
          </div>
        </div>
        <div v-else class="text-center text-medium-emphasis pa-4">
          {{ t("rom.no-notes") }}
        </div>
      </v-card-text>
    </v-card>
  </v-dialog>
</template>
