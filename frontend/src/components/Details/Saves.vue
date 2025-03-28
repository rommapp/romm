<script setup lang="ts">
import type { SaveSchema } from "@/__generated__";
import UploadSavesDialog from "@/components/common/Game/Dialog/Asset/UploadSaves.vue";
import DeleteSavesDialog from "@/components/common/Game/Dialog/Asset/DeleteSaves.vue";
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
const selectedSaves = ref<SaveSchema[]>([]);
const emitter = inject<Emitter<Events>>("emitter");

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
    class="rounded"
    return-object
    v-model="selectedSaves"
    show-select
    id="saves-table"
  >
    <template #header.actions>
      <v-btn-group divided density="compact">
        <v-btn
          v-if="scopes.includes('assets.write')"
          drawer
          size="small"
          @click="emitter?.emit('addSavesDialog', rom)"
        >
          <v-icon>mdi-upload</v-icon>
        </v-btn>
        <v-btn
          drawer
          :disabled="!selectedSaves.length"
          :variant="selectedSaves.length > 0 ? 'flat' : 'plain'"
          size="small"
          @click="downloasSaves"
        >
          <v-icon>mdi-download</v-icon>
        </v-btn>
        <v-btn
          v-if="scopes.includes('assets.write')"
          drawer
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
      ><span>{{ t("rom.no-saves-found") }}</span></template
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
  <delete-saves-dialog />
</template>

<style scoped>
#saves-table >>> .v-data-table__td {
  height: unset !important;
  padding-top: 4px;
  padding-bottom: 4px;
}

#saves-table >>> .v-data-table__td:last-child {
  padding-left: 0 !important;
}
</style>
