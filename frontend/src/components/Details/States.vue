<script setup lang="ts">
import type { StateSchema } from "@/__generated__";
import DeleteAssetDialog from "@/components/common/Game/Dialog/Asset/DeleteAssets.vue";
import UploadStatesDialog from "@/components/common/Game/Dialog/Asset/UploadStates.vue";
import { type DetailedRom } from "@/stores/roms";
import type { Events } from "@/types/emitter";
import { formatBytes, formatTimestamp } from "@/utils";
import type { Emitter } from "mitt";
import { inject, ref } from "vue";
import { useDisplay } from "vuetify";
import { useI18n } from "vue-i18n";
import storeAuth from "@/stores/auth";
import { storeToRefs } from "pinia";

// Props
const { t } = useI18n();
const { mdAndUp } = useDisplay();
const auth = storeAuth();
const { scopes } = storeToRefs(auth);
const props = defineProps<{ rom: DetailedRom }>();
const selectedStates = ref<StateSchema[]>([]);
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
async function downloasStates() {
  selectedStates.value.map((state) => {
    const a = document.createElement("a");
    a.href = state.download_path;
    a.download = `${state.file_name}`;
    a.click();
  });

  selectedStates.value = [];
}
</script>

<template>
  <v-data-table-virtual
    :items="rom.user_states"
    :width="mdAndUp ? '60vw' : '95vw'"
    :headers="HEADERS"
    class="rounded"
    return-object
    v-model="selectedStates"
    show-select
  >
    <template #header.actions>
      <v-btn-group divided density="compact">
        <v-btn
          v-if="scopes.includes('assets.write')"
          drawer
          size="small"
          @click="emitter?.emit('addStatesDialog', rom)"
        >
          <v-icon>mdi-upload</v-icon>
        </v-btn>
        <v-btn
          drawer
          :disabled="!selectedStates.length"
          :variant="selectedStates.length > 0 ? 'flat' : 'plain'"
          size="small"
          @click="downloasStates"
        >
          <v-icon>mdi-download</v-icon>
        </v-btn>
        <v-btn
          v-if="scopes.includes('assets.write')"
          drawer
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
        <v-btn drawer :href="item.download_path" download size="small">
          <v-icon> mdi-download </v-icon>
        </v-btn>
        <v-btn
          v-if="scopes.includes('assets.write')"
          drawer
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
  </v-data-table-virtual>
  <upload-states-dialog />
  <delete-asset-dialog />
</template>
<style scoped>
.name-row {
  min-width: 300px;
}
</style>
