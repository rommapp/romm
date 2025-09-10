<script setup lang="ts">
import type { Emitter } from "mitt";
import { inject, ref } from "vue";
import { useDisplay } from "vuetify";
import type { StateSchema } from "@/__generated__";
import RDialog from "@/components/common/RDialog.vue";
import stateApi from "@/services/api/state";
import storeRoms, { type DetailedRom } from "@/stores/roms";
import type { Events } from "@/types/emitter";
import { formatBytes } from "@/utils";

const { mdAndUp, smAndUp } = useDisplay();
const romsStore = storeRoms();
const show = ref(false);
const romRef = ref<DetailedRom | null>(null);
const statesRef = ref<StateSchema[]>([]);
const emitter = inject<Emitter<Events>>("emitter");

emitter?.on("showDeleteStatesDialog", ({ rom, states }) => {
  statesRef.value = states;
  romRef.value = rom;
  show.value = true;
});
const HEADERS = [
  {
    title: "Name",
    align: "start",
    sortable: true,
    key: "file_name",
  },
] as const;

async function deleteStates() {
  if (!statesRef.value) return;

  try {
    const { data } = await stateApi.deleteStates({
      states: statesRef.value,
    });

    if (romRef.value?.user_states) {
      const deletedAssetIds = statesRef.value.map((asset) => asset.id);
      romRef.value.user_states =
        romRef.value.user_states?.filter(
          (asset) => !deletedAssetIds.includes(asset.id),
        ) ?? [];
      romsStore.update(romRef.value);
    }

    emitter?.emit("snackbarShow", {
      msg: `Successfully deleted ${data.length} states`,
      icon: "mdi-check-circle",
      color: "green",
      timeout: 4000,
    });

    closeDialog();
  } catch (error) {
    emitter?.emit("snackbarShow", {
      msg: `Unable to delete states: ${error}`,
      icon: "mdi-close-circle",
      color: "red",
      timeout: 4000,
    });
  }
}

function closeDialog() {
  statesRef.value = [];
  show.value = false;
}
</script>

<template>
  <RDialog
    v-model="show"
    scroll-content
    :width="mdAndUp ? '50vw' : '95vw'"
    @close="closeDialog"
  >
    <template #header>
      <v-row no-gutters class="justify-center">
        Deleting {{ statesRef.length }} states of {{ romRef?.name }} from RomM
      </v-row>
    </template>
    <template #content>
      <v-data-table-virtual
        :item-value="(item) => item.id"
        :items="statesRef"
        :width="mdAndUp ? '60vw' : '95vw'"
        :headers="HEADERS"
      >
        <template #item.file_name="{ item }">
          <v-list-item class="px-0">
            <v-row no-gutters>
              <v-col>
                <template v-if="!smAndUp">
                  <v-chip size="x-small" label>
                    {{ formatBytes(item.file_size_bytes) }}
                  </v-chip>
                  <v-chip
                    v-if="item.emulator"
                    size="x-small"
                    class="ml-1 text-orange"
                    label
                  >
                    {{ item.emulator }}
                  </v-chip>
                </template>
                {{ item.file_name }}
                <v-chip label size="x-small" class="text-romm-red ml-2">
                  Removing from filesystem
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
                >
                  {{ item.emulator }}
                </v-chip>
                <v-chip class="ml-1" size="x-small" label>
                  {{ formatBytes(item.file_size_bytes) }}
                </v-chip>
              </template>
            </template>
          </v-list-item>
        </template>
      </v-data-table-virtual>
    </template>
    <template #append>
      <v-row no-gutters>
        <v-col>
          <v-list-item class="text-center mt-2">
            <span class="text-romm-red text-body-1">
              WARNING: These state will be removed from the filesystem. This
              action is irreversible!
            </span>
          </v-list-item>
        </v-col>
      </v-row>
      <v-row class="justify-center my-2">
        <v-btn-group divided density="compact">
          <v-btn class="bg-toplayer" variant="flat" @click="closeDialog">
            Cancel
          </v-btn>
          <v-btn
            class="text-romm-red bg-toplayer"
            variant="flat"
            @click="deleteStates"
          >
            Confirm
          </v-btn>
        </v-btn-group>
      </v-row>
    </template>
  </RDialog>
</template>
