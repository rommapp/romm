<script setup lang="ts">
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { inject, onBeforeUnmount, ref } from "vue";
import platformApi from "@/services/api/platform";

// Props
const show = ref(false);
const fsSlugToCreate = ref();
const slugToCreate = ref();
const emitter = inject<Emitter<Events>>("emitter");
emitter?.on("showAddPlatformDialog", () => {
  show.value = true;
});

// Functions
function addPlatform() {
  platformApi
    .uploadPlatform({ fsSlug: fsSlugToCreate.value })
    .then(() => {
      emitter?.emit("snackbarShow", {
        msg: `Platform ${fsSlugToCreate.value} created successfully!`,
        icon: "mdi-check-bold",
        color: "green",
        timeout: 2000,
      });
      closeDialog();
    })
    .catch((error) => {
      console.log(error);
      emitter?.emit("snackbarShow", {
        msg: error.response.data.detail,
        icon: "mdi-close-circle",
        color: "red",
      });
    })
    .finally(() => {
      emitter?.emit("showLoadingDialog", { loading: false, scrim: false });
    });
}

function closeDialog() {
  show.value = false;
  fsSlugToCreate.value = null;
}

onBeforeUnmount(() => {
  emitter?.off("showAddPlatformDialog");
});
</script>

<template>
  <v-dialog
    :modelValue="show"
    max-width="500px"
    scroll-strategy="none"
    :scrim="true"
    @click:outside="closeDialog"
    @keydown.esc="closeDialog"
    no-click-animation
    persistent
  >
    <v-card>
      <v-toolbar density="compact" class="bg-terciary">
        <v-row class="align-center" no-gutters>
          <v-col cols="10">
            <v-icon icon="mdi-controller" class="ml-5 mr-2" />
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
          <v-text-field
            @keyup.enter=""
            v-model="fsSlugToCreate"
            label="Platform name (folder name)"
            variant="outlined"
            required
            hide-details
          />
        </v-row>
        <v-row class="justify-center pa-2" no-gutters>
          <v-btn @click="closeDialog" class="bg-terciary">Cancel</v-btn>
          <v-btn
            @click="addPlatform()"
            class="text-romm-green bg-terciary ml-5"
          >
            Confirm
          </v-btn>
        </v-row>
      </v-card-text>
    </v-card>
  </v-dialog>
</template>

<style scoped></style>
