<script setup lang="ts">
import type { StateSchema } from "@/__generated__";
import RDialog from "@/components/common/RDialog.vue";
import type { DetailedRom } from "@/stores/roms";
import type { Events } from "@/types/emitter";
import { formatTimestamp } from "@/utils";
import type { Emitter } from "mitt";
import { inject, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { useDisplay } from "vuetify";

// Props
const { t } = useI18n();
const { mdAndUp } = useDisplay();
const show = ref(false);
const rom = ref<DetailedRom | null>(null);
const selectedStates = ref<StateSchema[]>([]);

const emitter = inject<Emitter<Events>>("emitter");
emitter?.on("selectStateDialog", (selectedRom) => {
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
  if (selectedStates.value.length == 0) return;
  emitter?.emit("stateSelected", selectedStates.value[0]);
  closeDialog();
}

function closeDialog() {
  show.value = false;
  rom.value = null;
  selectedStates.value = [];
}

watch(
  () => selectedStates.value,
  () => {
    if (selectedStates.value.length == 0) return;
    emitter?.emit("stateSelected", selectedStates.value[0]);
    closeDialog();
  },
);
</script>

<template>
  <r-dialog
    @close="closeDialog"
    v-model="show"
    icon="mdi-format-wrap-square"
    scroll-content
    :width="mdAndUp ? '50vw' : '95vw'"
    id="select-state-dialog"
  >
    <template #content>
      <v-data-table-virtual
        v-if="rom"
        :items="rom.user_states"
        :width="mdAndUp ? '60vw' : '95vw'"
        :headers="HEADERS"
        return-object
        class="rounded"
        show-select
        v-model="selectedStates"
        select-strategy="single"
      >
        <template #item.screenshot="{ item }">
          <v-img
            v-if="item.screenshot"
            :src="item.screenshot.download_path"
            height="135"
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
          <v-chip v-if="item.emulator" size="x-small" color="orange" label
            >{{ item.emulator }}
          </v-chip>
        </template>
        <template #no-data>
          <span>{{ t("rom.no-states-found") }}</span>
        </template>
      </v-data-table-virtual>
    </template>
    <template #append>
      <v-row class="justify-center my-2">
        <v-btn class="bg-toplayer" variant="flat" @click="closeDialog">
          Cancel
        </v-btn>
      </v-row>
    </template>
  </r-dialog>
</template>

<style>
#select-state-dialog .v-data-table__td {
  height: unset !important;
  padding-top: 4px;
  padding-bottom: 4px;
}

#select-state-dialog .v-data-table__td:nth-child(2) {
  min-height: 150px !important;
  min-width: 170px !important;
}
</style>
