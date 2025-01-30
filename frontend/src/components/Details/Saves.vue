<script setup lang="ts">
import type { SaveSchema } from "@/__generated__";
import DeleteAssetDialog from "@/components/common/Game/Dialog/Asset/DeleteAssets.vue";
import UploadSavesDialog from "@/components/common/Game/Dialog/Asset/UploadSaves.vue";
import { type DetailedRom } from "@/stores/roms";
import type { Events } from "@/types/emitter";
import { formatBytes, formatTimestamp } from "@/utils";
import type { Emitter } from "mitt";
import { inject, ref } from "vue";
import { useDisplay } from "vuetify";
import { useI18n } from "vue-i18n";

// Props
const { t } = useI18n();
const { mdAndUp } = useDisplay();
const props = defineProps<{ rom: DetailedRom }>();
const selectedSaves = ref<SaveSchema[]>([]);
const emitter = inject<Emitter<Events>>("emitter");
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
</script>

<template>
  <v-data-table-virtual
    :items="rom.user_saves"
    :width="mdAndUp ? '60vw' : '95vw'"
    :headers="HEADERS"
    return-object
    class="rounded"
    v-model="selectedSaves"
    show-select
  >
    <template #header.actions>
      <v-btn-group divided density="compact">
        <v-btn
          size="small"
          @click="emitter?.emit('addSavesDialog', rom)"
        >
          <v-icon>mdi-upload</v-icon>
        </v-btn>
        <v-btn
          :disabled="!selectedSaves.length"
          :variant="selectedSaves.length > 0 ? 'flat' : 'plain'"
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
          :variant="selectedSaves.length > 0 ? 'flat' : 'plain'"
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
    </template>
    <template #item.file_name="{ item }">
      <td class="name-row">
        <span>{{ item.file_name }}</span>
      </td>
    </template>
    <template #item.emulator="{ item }">
      <v-chip size="x-small" color="orange" label>{{ item.emulator }} </v-chip>
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
      ><span>{{ t("rom.no-saves-found") }}</span></template
    >
    <template #item.actions="{ item }">
      <v-btn-group divided density="compact">
        <v-btn
          :href="item.download_path"
          download
          size="small"
        >
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
  </v-data-table-virtual>
  <upload-saves-dialog />
  <delete-asset-dialog />
</template>
<style scoped>
.name-row {
  min-width: 350px;
}
</style>
