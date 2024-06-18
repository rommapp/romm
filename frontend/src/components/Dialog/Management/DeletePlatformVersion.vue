<script setup lang="ts">
import configApi from "@/services/api/config";
import storeConfig from "@/stores/config";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { inject, ref } from "vue";

// Props
const show = ref(false);
const emitter = inject<Emitter<Events>>("emitter");
const configStore = storeConfig();
const fsSlugToDelete = ref();
const slugToDelete = ref();
emitter?.on("showDeletePlatformVersionDialog", ({ fsSlug, slug }) => {
  fsSlugToDelete.value = fsSlug;
  slugToDelete.value = slug;
  show.value = true;
});

// Functions
function removeVersionPlatform() {
  configApi
    .deletePlatformVersionConfig({ fsSlug: fsSlugToDelete.value })
    .then(() => {
      configStore.removePlatformVersion(fsSlugToDelete.value);
    })
    .catch(({ response, message }) => {
      emitter?.emit("snackbarShow", {
        msg: `${response?.data?.detail || response?.statusText || message}`,
        icon: "mdi-close-circle",
        color: "red",
        timeout: 4000,
      });
    });
  closeDialog();
}

function closeDialog() {
  show.value = false;
}
</script>
<template>
  <!-- TODO: unify refactor dialog -->
  <v-dialog
    v-model="show"
    width="auto"
    no-click-animation
    persistent
    :scrim="true"
    @click:outside="closeDialog"
    @keydown.esc="closeDialog"
  >
    <v-card>
      <v-toolbar density="compact" class="bg-terciary">
        <v-row class="align-center" no-gutters>
          <v-col cols="10">
            <v-icon icon="mdi-delete" class="ml-5 mr-2" />
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
        <v-row class="justify-center pa-2" no-gutters>
          <span class="mr-1">Deleting platform version [</span>
          <span class="text-romm-accent-1 mr-1">{{ fsSlugToDelete }}</span>
          <span>:</span>
          <span class="text-romm-accent-1 ml-1">{{ slugToDelete }}</span
          ><span class="ml-1">].</span>
          <span class="ml-1">Do you confirm?</span>
        </v-row>
        <v-row class="justify-center pa-2" no-gutters>
          <v-btn class="bg-terciary" @click="closeDialog"> Cancel </v-btn>
          <v-btn
            class="text-romm-red bg-terciary ml-5"
            @click="removeVersionPlatform"
          >
            Confirm
          </v-btn>
        </v-row>
      </v-card-text>
    </v-card>
  </v-dialog>
</template>
