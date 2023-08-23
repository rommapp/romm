<script setup>
import { ref, inject } from "vue";
import { useRouter } from "vue-router";
import { useDisplay } from "vuetify";
import { deleteRomsApi } from "@/services/api";
import romsStore from "@/stores/roms";

const { xs, mdAndDown, lgAndUp } = useDisplay();
const router = useRouter();
const show = ref(false);
const storeRoms = romsStore();
const roms = ref();
const deleteFromFs = ref(false);

const emitter = inject("emitter");
emitter.on("showDeleteRomDialog", (romsToDelete) => {
  roms.value = romsToDelete;
  show.value = true;
});

async function deleteRoms() {
  await deleteRomsApi(roms.value, deleteFromFs.value)
    .then((response) => {
      emitter.emit("snackbarShow", {
        msg: response.data.msg,
        icon: "mdi-check-bold",
        color: "green",
      });
      storeRoms.reset();
    })
    .catch((error) => {
      console.log(error);
      emitter.emit("snackbarShow", {
        msg: error.response.data.detail,
        icon: "mdi-close-circle",
        color: "red",
      });
      return;
    });
  await router.push({
    name: "platform",
    params: { platform: roms.value[0].p_slug },
  });
  emitter.emit("refreshView");
  emitter.emit("refreshDrawer");
  show.value = false;
}
</script>

<template>
  <v-dialog
    :modelValue="show"
    width="auto"
    @click:outside="show = false"
    @keydown.esc="show = false"
    no-click-animation
    persistent
  >
    <v-card
      rounded="0"
      :class="{
        'delete-content': lgAndUp,
        'delete-content-tablet': mdAndDown,
        'delete-content-mobile': xs,
      }"
    >
      <v-toolbar density="compact" class="bg-terciary">
        <v-row class="align-center" no-gutters>
          <v-col cols="9" xs="9" sm="10" md="10" lg="11">
            <v-icon icon="mdi-delete" class="ml-5" />
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
          <span>Deleting the following</span>
          <span class="text-romm-accent-2 mx-1">{{ roms.length }}</span>
          <span>games. Do you confirm?</span>
        </v-row>
      </v-card-text>
      <v-card-text class="scroll bg-terciary py-0">
        <v-row class="justify-center pa-2" no-gutters>
          <v-list class="bg-terciary py-0">
            <v-list-item v-for="rom in roms" class="justify-center bg-terciary"
              >{{ rom.r_name }} - [<span class="text-romm-accent-1">{{
                rom.file_name
              }}</span
              >]</v-list-item
            >
          </v-list>
        </v-row>
      </v-card-text>
      <v-card-text>
        <v-row class="justify-center pa-2" no-gutters>
          <v-btn @click="show = false" class="bg-terciary">Cancel</v-btn>
          <v-btn @click="deleteRoms()" class="text-romm-red bg-terciary ml-5"
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
.scroll {
  overflow-y: scroll;
}
</style>
