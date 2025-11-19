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
  <v-dialog v-model="show" max-width="800" scrollable>
    <v-card>
      <v-card-title class="d-flex align-center">
        <v-icon class="mr-2">mdi-notebook</v-icon>
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
          <v-expansion-panels multiple flat variant="accordion">
            <v-expansion-panel
              v-for="(note, title) in rom.rom_user.notes"
              :key="title"
              rounded="0"
            >
              <v-expansion-panel-title class="bg-surface-variant">
                <div class="d-flex justify-space-between align-center w-100">
                  <span class="text-body-1">{{ title }}</span>
                  <v-chip
                    :color="note.is_public ? 'success' : 'warning'"
                    size="small"
                    variant="outlined"
                    class="mr-4"
                  >
                    <v-icon size="small" class="mr-1">
                      {{
                        note.is_public ? "mdi-lock-open-variant" : "mdi-lock"
                      }}
                    </v-icon>
                    {{ note.is_public ? t("rom.public") : t("rom.private") }}
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
                  class="text-caption mt-2"
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
      </v-card-text>
    </v-card>
  </v-dialog>
</template>
