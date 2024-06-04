<script setup lang="ts">
import configApi from "@/services/api/config";
import storeConfig from "@/stores/config";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { inject, ref } from "vue";

// Props
const show = ref(false);
const configStore = storeConfig();
const emitter = inject<Emitter<Events>>("emitter");
const fsSlugToCreate = ref();
const slugToCreate = ref();
emitter?.on("showCreatePlatformBindingDialog", ({ fsSlug = "", slug = "" }) => {
  fsSlugToCreate.value = fsSlug;
  slugToCreate.value = slug;
  show.value = true;
});

// Functions
function addBindPlatform() {
  configApi
    .addPlatformBindConfig({
      fsSlug: fsSlugToCreate.value,
      slug: slugToCreate.value,
    })
    .then(() => {
      configStore.addPlatformBinding(fsSlugToCreate.value, slugToCreate.value);
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
          <v-text-field
            v-model="fsSlugToCreate"
            label="Folder name"
            variant="outlined"
            required
            hide-details
          />
          <v-icon icon="mdi-menu-right" class="mx-2 text-romm-gray" />
          <v-text-field
            v-model="slugToCreate"
            class="text-romm-accent-1"
            label="RomM platform"
            color="romm-accent-1"
            base-color="romm-accent-1"
            variant="outlined"
            required
            hide-details
            @click="addBindPlatform"
          />
        </v-row>
        <v-row class="justify-center pa-2" no-gutters>
          <v-btn class="bg-terciary" @click="closeDialog"> Cancel </v-btn>
          <v-btn
            class="text-romm-green bg-terciary ml-5"
            @click="addBindPlatform"
          >
            Confirm
          </v-btn>
        </v-row>
      </v-card-text>
    </v-card>
  </v-dialog>
</template>
