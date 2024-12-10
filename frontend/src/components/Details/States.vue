<script setup lang="ts">
import type { StateSchema } from "@/__generated__";
import DeleteAssetDialog from "@/components/common/Game/Dialog/Asset/DeleteAssets.vue";
import UploadStatesDialog from "@/components/common/Game/Dialog/Asset/UploadStates.vue";
import { type DetailedRom } from "@/stores/roms";
import type { Events } from "@/types/emitter";
import { formatBytes, formatTimestamp } from "@/utils";
import type { Emitter } from "mitt";
import { inject, onMounted, ref, watch } from "vue";
import { useDisplay } from "vuetify";
import { useI18n } from "vue-i18n";

// Props
const { t } = useI18n();
const { xs, mdAndUp } = useDisplay();
const props = defineProps<{ rom: DetailedRom }>();
const selectedStates = ref<StateSchema[]>([]);
const emitter = inject<Emitter<Events>>("emitter");
// emitter?.on("romUpdated", (romUpdated) => {});
const HEADERS = [
  {
    title: "Name",
    align: "start",
    sortable: true,
    key: "file_name",
  },
  {
    title: "Core",
    align: "start",
    sortable: true,
    key: "emulator",
  },
  {
    title: "Updated",
    align: "start",
    sortable: true,
    key: "updated_at",
  },
  {
    title: "Size",
    align: "start",
    sortable: true,
    key: "file_size_bytes",
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
  if (props.rom.user_states) {
    pageCount.value = Math.ceil(
      props.rom.user_states.length / itemsPerPage.value,
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
    :items="rom.user_states"
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
          @click="emitter?.emit('addStatesDialog', rom)"
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
        <span>{{ item.file_name }}</span>
      </td>
    </template>
    <template #item.emulator="{ item }">
      <v-chip size="x-small" color="orange" label>{{ item.emulator }}</v-chip>
    </template>
    <template #item.updated_at="{ item }">
      <v-chip size="x-small" label>
        {{ formatTimestamp(item.updated_at) }}
      </v-chip>
    </template>
    <template #item.file_size_bytes="{ item }">
      <v-chip size="x-small" label
        >{{ formatBytes(item.file_size_bytes) }}
      </v-chip>
    </template>
    <template #no-data
      ><span>{{ t("rom.no-states-found") }}</span></template
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
  <delete-asset-dialog />
</template>
<style scoped>
.name-row {
  min-width: 300px;
}
</style>
