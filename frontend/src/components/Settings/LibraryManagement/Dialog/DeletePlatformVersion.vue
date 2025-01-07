<script setup lang="ts">
import PlatformIcon from "@/components/common/Platform/Icon.vue";
import RDialog from "@/components/common/RDialog.vue";
import configApi from "@/services/api/config";
import storeConfig from "@/stores/config";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { inject, ref } from "vue";
import { useDisplay } from "vuetify";

// Props
const { lgAndUp } = useDisplay();
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
function deleteVersionPlatform() {
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
  <r-dialog
    @close="closeDialog"
    v-model="show"
    icon="mdi-delete"
    :width="lgAndUp ? '45vw' : '95vw'"
  >
    <template #content>
      <v-row class="justify-center pa-2 align-center" no-gutters>
        <span class="mr-1">Deleting platform binding</span>
        <platform-icon class="mx-2" :key="slugToDelete" :slug="slugToDelete" />
        <span>[</span>
        <span class="text-romm-accent-1 ml-1"> {{ fsSlugToDelete }}</span>
        <span class="mx-1">:</span>
        <span class="text-romm-accent-1">{{ slugToDelete }}</span>
        <span class="ml-1">].</span>
        <span class="ml-1">Do you confirm?</span>
      </v-row>
    </template>
    <template #append>
      <v-row class="justify-center mb-2" no-gutters>
        <v-btn-group divided density="compact">
          <v-btn class="bg-terciary" @click="closeDialog"> Cancel </v-btn>
          <v-btn
            class="bg-terciary text-romm-red"
            @click="deleteVersionPlatform"
          >
            Confirm
          </v-btn>
        </v-btn-group>
      </v-row>
    </template>
  </r-dialog>
</template>
