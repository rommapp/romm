<script setup lang="ts">
import type { SaveSchema } from "@/__generated__";
import saveApi from "@/services/api/save";
import UploadSavesDialog from "@/components/Dialog/Asset/UploadSaves.vue";
import storeRoms, { type DetailedRom } from "@/stores/roms";
import type { Events } from "@/types/emitter";
import { formatBytes } from "@/utils";
import type { Emitter } from "mitt";
import { inject, onMounted, ref, watch } from "vue";
import { useDisplay } from "vuetify";

// Props
const { smAndUp, mdAndUp } = useDisplay();
const props = defineProps<{ rom: DetailedRom }>();
const romRef = ref<DetailedRom>(props.rom);
const selectedSaves = ref<SaveSchema[]>([]);
const emitter = inject<Emitter<Events>>("emitter");
emitter?.on("romUpdated", (romUpdated) => {
  if (romUpdated?.id === romRef.value.id) {
    romRef.value.user_saves = romUpdated.user_saves;
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
async function downloasSaves() {
  selectedSaves.value.map((save) => {
    const a = document.createElement("a");
    a.href = save.download_path;
    a.download = `${save.file_name}`;
    a.click();
  });

  selectedSaves.value = [];
}

function updateDataTablePages() {
  if (romRef.value.user_saves) {
    pageCount.value = Math.ceil(
      romRef.value.user_saves.length / itemsPerPage.value
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
    :items="romRef.user_saves"
    :width="mdAndUp ? '60vw' : '95vw'"
    :items-per-page="itemsPerPage"
    :items-per-page-options="PER_PAGE_OPTIONS"
    :headers="HEADERS"
    return-object
    v-model="selectedSaves"
    v-model:page="page"
    show-select
  >
    <template #header.actions>
      <v-btn
        prepend-icon="mdi-plus"
        class="text-romm-accent-1"
        variant="outlined"
        @click="emitter?.emit('addSavesDialog', romRef)"
      >
        Add
      </v-btn>
    </template>
    <template #item.file_name="{ item }">
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
    </template>
    <template #no-data
      ><span>No saves found for {{ romRef?.name }}</span></template
    >
    <template #item.actions="{ item }">
      <v-btn-group divided density="compact">
        <v-btn :href="item.download_path" download size="small">
          <v-icon> mdi-download </v-icon>
        </v-btn>
        <v-btn
          size="small"
          @click="
            emitter?.emit('showDeleteSavesDialog', {
              rom: props.rom,
              saves: [item],
            })
          "
        >
          <v-icon class="text-romm-red">mdi-delete</v-icon>
        </v-btn>
      </v-btn-group>
    </template>
    <template #bottom>
      <v-divider />
      <v-row no-gutters class="pt-2 align-center justify-center">
        <v-btn-group class="px-2" divided density="compact">
          <v-btn
            :disabled="!selectedSaves.length"
            size="small"
            @click="downloasSaves"
          >
            <v-icon>mdi-download</v-icon>
          </v-btn>
          <v-btn
            :class="{
              'text-romm-red': selectedSaves.length,
            }"
            :disabled="!selectedSaves.length"
            @click="
              emitter?.emit('showDeleteSavesDialog', {
                rom: props.rom,
                saves: selectedSaves,
              })
            "
            size="small"
          >
            <v-icon>mdi-delete</v-icon>
          </v-btn>
        </v-btn-group>
        <v-col class="px-6">
          <v-pagination
            v-model="page"
            rounded="0"
            :show-first-last-page="true"
            active-color="romm-accent-1"
            :length="pageCount"
          />
        </v-col>
        <v-col cols="5" sm="3" xl="2">
          <v-select
            v-model="itemsPerPage"
            class="pa-2"
            label="Assets per page"
            density="compact"
            variant="outlined"
            :items="PER_PAGE_OPTIONS"
            hide-details
          />
        </v-col>
      </v-row>
    </template>
  </v-data-table>
  <upload-saves-dialog />
</template>
