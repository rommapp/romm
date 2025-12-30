<script setup lang="ts">
import type { Emitter } from "mitt";
import { inject, ref } from "vue";
import { useI18n } from "vue-i18n";
import MultiNoteManager from "@/components/Details/MultiNoteManager.vue";
import RDialog from "@/components/common/RDialog.vue";
import romApi from "@/services/api/rom";
import type { DetailedRom } from "@/stores/roms";
import type { Events } from "@/types/emitter";

const emitter = inject<Emitter<Events>>("emitter");
const { t } = useI18n();

const rom = ref<DetailedRom | null>(null);
const show = ref(false);

emitter?.on("showNoteDialog", async (romToShow) => {
  show.value = true;

  if (romToShow.id) {
    try {
      const response = await romApi.getRom({ romId: romToShow.id });
      rom.value = response.data;
    } catch (error) {
      console.error("Failed to fetch ROM details:", error);
      rom.value = null;
    }
  }
});

async function onNotesUpdated() {
  if (rom.value?.id) {
    try {
      const updatedRom = await romApi.getRom({ romId: rom.value.id });
      // Update the rom with the new data
      Object.assign(rom.value, updatedRom.data);
    } catch (error) {
      console.error("Failed to refetch ROM data:", error);
    }
  }
}

function closeDialog() {
  show.value = false;
  rom.value = null;
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
      <div class="pa-2">
        <MultiNoteManager :rom="rom" @notes-updated="onNotesUpdated" />
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
