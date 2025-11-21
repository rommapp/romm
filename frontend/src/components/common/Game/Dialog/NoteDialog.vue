<script setup lang="ts">
import { MdPreview } from "md-editor-v3";
import "md-editor-v3/lib/style.css";
import type { Emitter } from "mitt";
import { inject, ref, computed } from "vue";
import { useI18n } from "vue-i18n";
import { useTheme } from "vuetify";
import RDialog from "@/components/common/RDialog.vue";
import romApi from "@/services/api/rom";
import type { SimpleRom } from "@/stores/roms";
import type { Events } from "@/types/emitter";

const theme = useTheme();
const emitter = inject<Emitter<Events>>("emitter");
const { t } = useI18n();

const rom = ref<SimpleRom | null>(null);
const show = ref(false);
const notes = ref<any[]>([]);
const loading = ref(false);

// Computed to get current user notes
const currentUserNotes = computed(() => {
  return notes.value
    .filter((note) => note.user_id === rom.value?.rom_user?.user_id)
    .sort((a, b) => a.title.localeCompare(b.title));
});

emitter?.on("showNoteDialog", async (romToShow) => {
  rom.value = romToShow;
  show.value = true;

  // Fetch notes for this ROM
  if (romToShow.id) {
    loading.value = true;
    try {
      const response = await romApi.getRomNotes({ romId: romToShow.id });
      notes.value = response.data;
    } catch (error) {
      console.error("Failed to fetch notes:", error);
      notes.value = [];
    } finally {
      loading.value = false;
    }
  }
});

function closeDialog() {
  show.value = false;
  rom.value = null;
  notes.value = [];
}
</script>

<template>
  <RDialog
    v-if="rom"
    v-model="show"
    icon="mdi-notebook"
    scroll-content
    width="800"
    @close="closeDialog"
  >
    <template #header>
      <v-toolbar-title>
        {{ t("rom.my-notes") }} - {{ rom.name }}
      </v-toolbar-title>
    </template>
    <template #content>
      <div class="pa-4">
        <div v-if="loading" class="text-center py-8">
          <v-progress-circular indeterminate color="primary" />
          <p class="text-body-2 mt-2">{{ t("common.loading") }}...</p>
        </div>
        <div v-else-if="currentUserNotes.length > 0">
          <v-expansion-panels multiple flat variant="accordion">
            <v-expansion-panel
              v-for="note in currentUserNotes"
              :key="note.title"
              :value="note.title"
              rounded="0"
            >
              <v-expansion-panel-title class="bg-toplayer">
                <div class="d-flex justify-space-between align-center w-100">
                  <span class="text-body-1">{{ note.title }}</span>
                  <div class="d-flex gap-2 align-center mr-4">
                    <v-chip
                      :color="note.is_public ? 'success' : 'warning'"
                      variant="text"
                      class="mr-2"
                    >
                      <v-icon>
                        {{
                          note.is_public ? "mdi-lock-open-variant" : "mdi-lock"
                        }}
                      </v-icon>
                    </v-chip>
                  </div>
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
        </div>
        <div v-else class="text-center py-8">
          <v-icon color="grey" size="64">mdi-note-text-outline</v-icon>
          <p class="text-h6 text-grey mt-4 mb-2">{{ t("rom.no-notes") }}</p>
          <p class="text-body-2 text-grey">{{ t("rom.no-notes-desc") }}</p>
        </div>
      </div>
    </template>
  </RDialog>
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
