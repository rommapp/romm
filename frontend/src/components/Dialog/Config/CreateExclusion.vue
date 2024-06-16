<script setup lang="ts">
import configApi from "@/services/api/config";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { inject, ref } from "vue";

// Props
const show = ref(false);
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
  <!-- TODO: unify refactor dialog -->
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
              class="bg-terciary"
              rounded="0"
              variant="text"
              icon="mdi-close"
              block
              @click="closeDialog"
            />
          </v-col>
        </v-row>
      </v-toolbar>
      <v-divider />

      <v-card-text>
        <v-row class="pa-2 align-center" no-gutters>
          <v-icon icon="mdi-menu-right" class="mx-2 text-romm-gray" />
          <v-text-field
            v-model="exclusionToCreate"
            class="text-romm-accent-1"
            label="RomM platform"
            color="romm-accent-1"
            base-color="romm-accent-1"
            variant="outlined"
            required
            hide-details
            @keyup.enter="addExclusion"
          />
        </v-row>
        <v-row class="justify-center pa-2" no-gutters>
          <v-btn class="bg-terciary" @click="closeDialog"> Cancel </v-btn>
          <v-btn class="text-romm-green bg-terciary ml-5" @click="addExclusion">
            Confirm
          </v-btn>
        </v-row>
      </v-card-text>
    </v-card>
  </v-dialog>
</template>
