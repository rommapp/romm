<script setup lang="ts">
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { inject, ref } from "vue";
import { useRouter } from "vue-router";
import { useDisplay } from "vuetify";

import romApi from "@/services/api/rom";
import storeRoms from "@/stores/roms";

const { xs, mdAndDown, lgAndUp } = useDisplay();
const router = useRouter();
const show = ref(false);
const romsStore = storeRoms();
const roms = ref();
const deleteFromFs = ref(false);

const emitter = inject<Emitter<Events>>("emitter");
emitter?.on("showDeleteRomDialog", (romsToDelete) => {
  roms.value = romsToDelete;
  show.value = true;
});

async function deleteRoms() {
  await romApi
    .deleteRoms({ roms: roms.value, deleteFromFs: deleteFromFs.value })
    .then((response) => {
      emitter?.emit("snackbarShow", {
        msg: response.data.msg,
        icon: "mdi-check-bold",
        color: "green",
      });
      romsStore.resetSelection();
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

  romsStore.remove(roms.value);
  emitter?.emit("refreshDrawer", null);
  closeDialog();

  await router.push({
    name: "platform",
    params: { platform: roms.value[0].platform_id },
  });
}

function closeDialog() {
  deleteFromFs.value = false;
  show.value = false;
}
</script>

<template>
  <v-dialog
    :model-value="show"
    width="auto"
    no-click-animation
    persistent
    :scrim="true"
    @click:outside="closeDialog"
    @keydown.esc="closeDialog"
  >
    <v-card
      rounded="0"
      :class="{
        'delete-content': lgAndUp,
        'delete-content-tablet': mdAndDown,
        'delete-content-mobile': xs,
      }"
    >
      <v-toolbar
        density="compact"
        class="bg-terciary"
      >
        <v-row
          class="align-center"
          no-gutters
        >
          <v-col
            cols="9"
            xs="9"
            sm="10"
            md="10"
            lg="11"
          >
            <v-icon
              icon="mdi-delete"
              class="ml-5"
            />
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
      <v-divider
        class="border-opacity-25"
        :thickness="1"
      />
      <v-card-text>
        <v-row
          class="justify-center pa-2"
          no-gutters
        >
          <span>Deleting the following</span>
          <span class="text-romm-accent-1 mx-1">{{ roms.length }}</span>
          <span>games. Do you confirm?</span>
        </v-row>
      </v-card-text>
      <v-card-text class="scroll bg-terciary py-0">
        <v-row
          class="justify-center pa-2"
          no-gutters
        >
          <v-list class="bg-terciary py-0">
            <v-list-item
              v-for="rom in roms"
              :key="rom.id"
              class="justify-center bg-terciary"
            >
              {{ rom.name }} - [<span class="text-romm-accent-1">{{
                rom.file_name
              }}</span>]
            </v-list-item>
          </v-list>
        </v-row>
      </v-card-text>
      <v-card-text>
        <v-row
          class="justify-center pa-2"
          no-gutters
        >
          <v-btn
            class="bg-terciary"
            @click="closeDialog"
          >
            Cancel
          </v-btn>
          <v-btn
            class="text-romm-red bg-terciary ml-5"
            @click="deleteRoms()"
          >
            Confirm
          </v-btn>
        </v-row>
      </v-card-text>

      <v-divider
        class="border-opacity-25"
        :thickness="1"
      />
      <v-toolbar
        class="bg-terciary"
        density="compact"
      >
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

<style scoped>
.delete-content {
  width: 900px;
  max-height: 600px;
}

.delete-content-tablet {
  width: 570px;
  max-height: 600px;
}

.delete-content-mobile {
  width: 85vw;
  max-height: 600px;
}
</style>
