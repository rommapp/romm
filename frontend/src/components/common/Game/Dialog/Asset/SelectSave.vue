<script setup lang="ts">
import type { SaveSchema } from "@/__generated__";
import RDialog from "@/components/common/RDialog.vue";
import type { DetailedRom } from "@/stores/roms";
import type { Events } from "@/types/emitter";
import { formatTimestamp } from "@/utils";
import type { Emitter } from "mitt";
import { inject, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useDisplay } from "vuetify";

// Props
const { t } = useI18n();
const { mdAndUp } = useDisplay();
const show = ref(false);
const rom = ref<DetailedRom | null>(null);
const selectedSaves = ref<SaveSchema[]>([]);

const emitter = inject<Emitter<Events>>("emitter");
emitter?.on("selectSaveDialog", (selectedRom) => {
  rom.value = selectedRom;
  show.value = true;
});

const HEADERS = [
  {
    title: "Screenshot",
    align: "start",
    sortable: false,
    key: "screenshot",
  },
  {
    title: "Name",
    align: "start",
    sortable: true,
    key: "file_name",
  },
  {
    title: "Updated",
    align: "start",
    sortable: true,
    key: "updated_at",
  },
  {
    title: "Core",
    align: "start",
    sortable: true,
    key: "emulator",
  },
] as const;

function onLoad() {
  if (selectedSaves.value.length == 0) return;
  emitter?.emit("saveSelected", selectedSaves.value[0]);
  closeDialog();
}

function closeDialog() {
  show.value = false;
  rom.value = null;
  selectedSaves.value = [];
}
</script>

<template>
  <r-dialog
    @close="closeDialog"
    v-model="show"
    icon="mdi-format-wrap-square"
    scroll-content
    :width="mdAndUp ? '50vw' : '95vw'"
    id="select-save-dialog"
  >
    <template #content>
      <v-data-table-virtual
        v-if="rom"
        :items="rom.user_saves"
        :width="mdAndUp ? '60vw' : '95vw'"
        :headers="HEADERS"
        return-object
        class="rounded"
        show-select
        v-model="selectedSaves"
        select-strategy="single"
      >
        <template #item.screenshot="{ item }">
          <v-img
            v-if="item.screenshot"
            :src="item.screenshot.download_path"
            height="100"
            class="mr-2"
          />
        </template>
        <template #item.file_name="{ item }">
          <td class="name-row">
            <span>{{ item.file_name }}</span>
          </td>
        </template>
        <template #item.updated_at="{ item }">
          <v-chip size="x-small" label>
            {{ formatTimestamp(item.updated_at) }}
          </v-chip>
        </template>
        <template #item.emulator="{ item }">
          <v-chip size="x-small" color="orange" label
            >{{ item.emulator }}
          </v-chip>
        </template>
        <template #no-data>
          <span>{{ t("rom.no-saves-found") }}</span>
        </template>
      </v-data-table-virtual>
    </template>
    <template #append>
      <v-row class="justify-center my-2">
        <v-btn
          class="bg-toplayer"
          color="primary"
          variant="tonal"
          :disabled="selectedSaves.length == 0"
          @click="onLoad"
        >
          Load
        </v-btn>
      </v-row>
    </template>
  </r-dialog>
</template>

<style>
#select-save-dialog .v-data-table__td {
  height: 100px !important;
}
</style>
