<script setup lang="ts">
import type { StateSchema } from "@/__generated__";
import stateApi from "@/services/api/state";
import UploadStatesDialog from "@/components/Dialog/Asset/UploadStates.vue";
import storeRoms, { type DetailedRom } from "@/stores/roms";
import type { Events } from "@/types/emitter";
import { formatBytes } from "@/utils";
import type { Emitter } from "mitt";
import { inject, onMounted, ref, watch } from "vue";
import { useDisplay } from "vuetify";

// Props
const { xs, smAndUp, mdAndUp } = useDisplay();
const props = defineProps<{ rom: DetailedRom }>();
const romRef = ref<DetailedRom>(props.rom);
const selectedStates = ref<StateSchema[]>([]);
const emitter = inject<Emitter<Events>>("emitter");
emitter?.on("romUpdated", (romUpdated) => {
  if (romUpdated?.id === romRef.value.id) {
    romRef.value.user_states = romUpdated.user_states;
  }
});
const HEADERS = [
  {
    title: "Name",
    align: "start",
    sortable: true,
    key: "file_name",
  },
  { title: "", align: "end", key: "actions", sortable: false },
] as const;
const page = ref(1);
const itemsPerPage = ref(10);
const pageCount = ref(0);
const PER_PAGE_OPTIONS = [10, 25, 50, 100];

// Functions
async function downloasStates() {
  selectedStates.value.map((state) => {
    const a = document.createElement("a");
    a.href = state.download_path;
    a.download = `${state.file_name}`;
    a.click();
  });

  selectedStates.value = [];
}

function updateDataTablePages() {
  if (romRef.value.user_states) {
    pageCount.value = Math.ceil(
      romRef.value.user_states.length / itemsPerPage.value
    );
  }
}

watch(itemsPerPage, async () => {
  updateDataTablePages();
});

onMounted(() => {
  updateDataTablePages();
});
</script>

<template>
  <v-data-table
    :items="romRef.user_states"
    :width="mdAndUp ? '60vw' : '95vw'"
    :items-per-page="itemsPerPage"
    :items-per-page-options="PER_PAGE_OPTIONS"
    :headers="HEADERS"
    class="bg-secondary"
    return-object
    v-model="selectedStates"
    v-model:page="page"
    show-select
  >
    <template #header.actions>
      <v-btn-group divided density="compact">
        <v-btn
          class="bg-secondary"
          size="small"
          @click="emitter?.emit('addStatesDialog', romRef)"
        >
          <v-icon>mdi-upload</v-icon>
        </v-btn>
        <v-btn
          class="bg-secondary"
          :disabled="!selectedStates.length"
          :variant="selectedStates.length > 0 ? 'flat' : 'plain'"
          size="small"
          @click="downloasStates"
        >
          <v-icon>mdi-download</v-icon>
        </v-btn>
        <v-btn
          class="bg-secondary"
          :class="{
            'text-romm-red': selectedStates.length,
          }"
          :disabled="!selectedStates.length"
          :variant="selectedStates.length > 0 ? 'flat' : 'plain'"
          @click="
            emitter?.emit('showDeleteStatesDialog', {
              rom: props.rom,
              states: selectedStates,
            })
          "
          size="small"
        >
          <v-icon>mdi-delete</v-icon>
        </v-btn>
      </v-btn-group>
    </template>
    <template #item.file_name="{ item }">
      <td class="name-row">
        <v-list-item class="px-0">
          <v-row no-gutters>
            <v-col>
              {{ item.file_name }}
            </v-col>
          </v-row>
          <v-row v-if="!smAndUp" no-gutters>
            <v-col>
              <v-chip size="x-small" label
                >{{ formatBytes(item.file_size_bytes) }}
              </v-chip>
              <v-chip
                v-if="item.emulator"
                size="x-small"
                class="ml-1 text-orange"
                label
                >{{ item.emulator }}
              </v-chip>
            </v-col>
          </v-row>
          <template #append>
            <template v-if="smAndUp">
              <v-chip
                v-if="item.emulator"
                size="x-small"
                class="text-orange"
                label
                >{{ item.emulator }}
              </v-chip>
              <v-chip class="ml-1" size="x-small" label
                >{{ formatBytes(item.file_size_bytes) }}
              </v-chip>
            </template>
          </template>
        </v-list-item>
      </td>
    </template>
    <template #no-data
      ><span>No states found for {{ romRef?.name }}</span></template
    >
    <template #item.actions="{ item }">
      <v-btn-group divided density="compact">
        <v-btn
          class="bg-secondary"
          :href="item.download_path"
          download
          size="small"
        >
          <v-icon> mdi-download </v-icon>
        </v-btn>
        <v-btn
          class="bg-secondary"
          size="small"
          @click="
            emitter?.emit('showDeleteStatesDialog', {
              rom: props.rom,
              states: [item],
            })
          "
        >
          <v-icon class="text-romm-red">mdi-delete</v-icon>
        </v-btn>
      </v-btn-group>
    </template>
    <template #bottom>
      <v-divider />
      <v-row no-gutters class="pa-1 align-center justify-center">
        <v-col cols="8" sm="9" md="10" class="px-3">
          <v-pagination
            :show-first-last-page="!xs"
            v-model="page"
            rounded="0"
            active-color="romm-accent-1"
            :length="pageCount"
          />
        </v-col>
        <v-col>
          <v-select
            v-model="itemsPerPage"
            class="pa-2"
            label="Files per page"
            density="compact"
            variant="outlined"
            :items="PER_PAGE_OPTIONS"
            hide-details
          />
        </v-col>
      </v-row>
    </template>
  </v-data-table>
  <upload-states-dialog />
</template>
<style scoped>
.name-row {
  min-width: 350px;
}
</style>
