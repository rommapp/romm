<script setup lang="ts">
import { ref, inject } from "vue";
import { useRouter } from "vue-router";
import type { Emitter } from "mitt";
import type { Events } from "@/types/emitter";
import api from "@/services/api";
import storePlatforms, { type Platform } from "@/stores/platforms";

const router = useRouter();
const platformsStore = storePlatforms();
const platform = ref<Platform | null>(null);
const show = ref(false);
const emitter = inject<Emitter<Events>>("emitter");
emitter?.on("showDeletePlatformDialog", (platformToDelete) => {
  platform.value = platformToDelete;
  show.value = true;
});
const deleteFromFs = ref(false);

async function deletePlatform() {
  if (!platform.value) return;

  show.value = false;
  await api
    .deletePlatform({
      platform: platform.value,
      deleteFromFs: deleteFromFs.value,
    })
    .then((response) => {
      emitter?.emit("snackbarShow", {
        msg: response.data.msg,
        icon: "mdi-check-bold",
        color: "green",
      });
    })
    .catch((error) => {
      console.log(error);
      emitter?.emit("snackbarShow", {
        msg: error.response.data.detail,
        icon: "mdi-close-circle",
        color: "red",
      });
      return;
    });

  await router.push({ name: "dashboard" });

  platformsStore.remove(platform.value);
  emitter?.emit("refreshDrawer", null);
  closeDialog();
}

function closeDialog() {
  deleteFromFs.value = false;
  show.value = false;
}
</script>
<template>
  <v-dialog v-if="platform" v-model="show" max-width="500px" :scrim="true">
    <v-card>
      <v-toolbar density="compact" class="bg-terciary">
        <v-row class="align-center" no-gutters>
          <v-col cols="10">
            <v-icon icon="mdi-delete" class="ml-5 mr-2" />
          </v-col>
          <v-col>
            <v-btn
              @click="show = false"
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
          <span class="mr-1">Deleting platform</span
          ><span class="text-romm-accent-1"
            >{{ platform.name }} - [<span class="text-romm-accent-1">{{
              platform.fs_slug
            }}</span
            >]</span
          >.
          <span class="ml-1">Do you confirm?</span>
        </v-row>
        <v-row class="justify-center pa-2" no-gutters>
          <v-btn @click="show = false" class="bg-terciary">Cancel</v-btn>
          <v-btn
            class="bg-terciary text-romm-red ml-5"
            @click="deletePlatform()"
            >Confirm</v-btn
          >
        </v-row>
      </v-card-text>

      <v-divider class="border-opacity-25" :thickness="1" />
      <v-toolbar class="bg-terciary" density="compact">
        <v-checkbox
          v-model="deleteFromFs"
          label="Remove from filesystem"
          class="ml-3"
          hide-details
        />
      </v-toolbar>
    </v-card>
  </v-dialog>
</template>
