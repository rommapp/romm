<script setup lang="ts">
import { ref, inject } from "vue";
import type { Emitter } from "mitt";
import type { Events } from "@/types/emitter";
import storeConfig from "@/stores/config";
import configApi from "@/services/api/config";

// Props
const show = ref(false);
const configStore = storeConfig();
const emitter = inject<Emitter<Events>>("emitter");
const excludeToCreate = ref();
const exclusionToCreate = ref();
emitter?.on("showCreateExclusionDialog", ({ exclude }) => {
  excludeToCreate.value = exclude;
  show.value = true;
});

// Functions
function addExclusion() {
  configApi.addExclusion({
    exclude: excludeToCreate.value,
    exclusion: exclusionToCreate.value,
  });
  // configStore.addExclusion(exclusion);
  closeDialog();
}

function closeDialog() {
  show.value = false;
}
</script>
<template>
  <v-dialog v-model="show" max-width="500px" :scrim="true">
    <v-card>
      <v-toolbar density="compact" class="bg-terciary">
        <v-row class="align-center" no-gutters>
          <v-col cols="10">
            <v-icon icon="mdi-controller" class="ml-5" />
            <v-icon icon="mdi-menu-right" class="ml-1 text-romm-gray" />
            <v-icon icon="mdi-controller" class="ml-1 text-romm-accent-1" />
          </v-col>
          <v-col>
            <v-btn
              @click="closeDialog"
              class="bg-terciary"
              rounded="0"
              variant="text"
              icon="mdi-close"
              block
            />
          </v-col>
        </v-row>
      </v-toolbar>
      <v-divider class="border-opacity-25" :thickness="1" />

      <v-card-text>
        <v-row class="pa-2 align-center" no-gutters>
          <v-icon icon="mdi-menu-right" class="mx-2 text-romm-gray" />
          <v-text-field
            class="text-romm-accent-1"
            @keyup.enter=""
            v-model="exclusionToCreate"
            label="RomM platform"
            color="romm-accent-1"
            base-color="romm-accent-1"
            variant="outlined"
            required
            hide-details
          />
        </v-row>
        <v-row class="justify-center pa-2" no-gutters>
          <v-btn @click="closeDialog" class="bg-terciary">Cancel</v-btn>
          <v-btn
            @click="addExclusion()"
            class="text-romm-green bg-terciary ml-5"
          >
            Confirm
          </v-btn>
        </v-row>
      </v-card-text>
    </v-card>
  </v-dialog>
</template>
