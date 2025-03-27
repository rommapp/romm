<script setup lang="ts">
import type { StateSchema } from "@/__generated__";
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
const { lgAndUp } = useDisplay();
const auth = storeAuth();
const { scopes } = storeToRefs(auth);
const props = defineProps<{ rom: DetailedRom }>();
const selectedStates = ref<StateSchema[]>([]);
const emitter = inject<Emitter<Events>>("emitter");

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
    :headers="[
      lgAndUp
        ? {
            title: 'Screenshot',
            align: 'start',
            sortable: false,
            key: 'screenshot',
          }
        : {},
      {
        title: 'Name',
        align: 'start',
        sortable: true,
        key: 'file_name',
      },
      {
        title: 'Updated',
        align: 'center',
        sortable: true,
        key: 'updated_at',
      },
      { title: '', align: 'end', key: 'actions', sortable: false },
    ]"
    class="rounded states-table"
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
    <template #item.screenshot="{ item }">
      <v-img
        v-if="item.screenshot && lgAndUp"
        :src="item.screenshot.download_path"
        height="135"
        width="180"
        class="mr-2"
      />
      <div v-else style="height: 62px"></div>
    </template>
    <template #item.file_name="{ item }">
      <v-row style="min-width: auto">{{ item.file_name }}</v-row>
      <v-row class="mt-4" style="min-height: 20px">
        <v-chip
          v-if="item.emulator"
          size="x-small"
          color="orange"
          label
          class="mr-2"
          >{{ item.emulator }}</v-chip
        >
        <v-chip size="x-small" label
          >{{ formatBytes(item.file_size_bytes) }}
        </v-chip>
      </v-row>
    </template>
    <template #item.updated_at="{ item }">
      <v-chip size="x-small" label>
        {{ formatTimestamp(item.updated_at) }}
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
</template>

<style scoped>
.states-table >>> .v-data-table__td {
  height: unset !important;
  min-height: 62px;
}

.states-table >>> .v-data-table__td:last-child {
  padding-left: 0 !important;
}
</style>
