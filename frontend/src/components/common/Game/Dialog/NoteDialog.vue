<script setup lang="ts">
import { MdPreview } from "md-editor-v3";
import "md-editor-v3/lib/style.css";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { inject, ref } from "vue";
import type { SimpleRom } from "@/stores/roms";
import { useTheme } from "vuetify";
import { useI18n } from "vue-i18n";

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
        <v-icon class="mr-2">mdi-notebook</v-icon>
        {{ t("rom.my-notes") }} - {{ rom?.name }}
        <v-spacer />
        <v-btn icon @click="show = false">
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-card-title>
      <v-card-text class="pa-4">
        <div v-if="rom?.rom_user?.note_raw_markdown">
          <MdPreview
            :model-value="rom.rom_user.note_raw_markdown"
            :theme="theme.name.value == 'dark' ? 'dark' : 'light'"
            language="en-US"
            preview-theme="vuepress"
            code-theme="github"
            class="py-2"
          />
        </div>
        <div v-else class="text-center pa-4">
          <v-icon size="48" color="grey">mdi-notebook-outline</v-icon>
          <p class="text-grey mt-2">No notes available</p>
        </div>
      </v-card-text>
    </v-card>
  </v-dialog>
</template>

<style scoped>
/* Inherit markdown editor styles from the main application */
:deep(.md-editor-dark) {
  --md-bk-color: #161b22 !important;
}

:deep(.md-editor),
:deep(.md-preview) {
  line-height: 1.25 !important;
}

:deep(.md-editor-preview) {
  word-break: break-word !important;

  blockquote {
    border-left-color: rgba(var(--v-theme-secondary));
  }

  .md-editor-code-flag {
    visibility: hidden;
  }

  .md-editor-admonition {
    border-color: rgba(var(--v-theme-secondary));
    background-color: rgba(var(--v-theme-toplayer)) !important;
  }

  .md-editor-code summary,
  .md-editor-code code {
    background-color: rgba(var(--v-theme-toplayer)) !important;
  }
}

:deep(.vuepress-theme pre code) {
  background-color: #0d1117;
}
</style>
