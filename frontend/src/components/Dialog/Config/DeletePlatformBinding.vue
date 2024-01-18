<script setup lang="ts">
import api_config from "@/services/api_config";
import storeConfig from "@/stores/config";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { inject, ref } from "vue";

// Props
const show = ref(false);
const emitter = inject<Emitter<Events>>("emitter");
const configStore = storeConfig();
const platformBindingFSSlugToDelete = ref();
const platformBindingSlugToDelete = ref();
emitter?.on("showDeletePlatformBindingDialog", ({ fsSlug, slug }) => {
  platformBindingFSSlugToDelete.value = fsSlug;
  platformBindingSlugToDelete.value = slug;
  show.value = true;
});

// Functions
function removeBindPlatform() {
  api_config
    .deletePlatformBindConfig({ fsSlug: platformBindingFSSlugToDelete.value })
    .then(() => {
      configStore.removePlatformBinding(platformBindingFSSlugToDelete.value);
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
  <v-dialog
    v-model="show"
    width="auto"
    @click:outside="closeDialog"
    @keydown.esc="closeDialog"
    no-click-animation
    persistent
  >
    <v-card>
      <v-toolbar density="compact" class="bg-terciary">
        <v-row class="align-center" no-gutters>
          <v-col cols="10">
            <v-icon icon="mdi-delete" class="ml-5 mr-2" />
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
        <v-row class="justify-center pa-2" no-gutters>
          <span class="mr-1">Deleting platform binding [</span>
          <span class="text-romm-accent-1 mr-1">{{
            platformBindingFSSlugToDelete
          }}</span>
          <span>:</span>
          <span class="text-romm-accent-1 ml-1">{{
            platformBindingSlugToDelete
          }}</span
          ><span class="ml-1">].</span>
          <span class="ml-1">Do you confirm?</span>
        </v-row>
        <v-row class="justify-center pa-2" no-gutters>
          <v-btn @click="closeDialog" class="bg-terciary">Cancel</v-btn>
          <v-btn
            @click="removeBindPlatform()"
            class="text-romm-red bg-terciary ml-5"
          >
            Confirm
          </v-btn>
        </v-row>
      </v-card-text>
    </v-card>
  </v-dialog>
</template>
