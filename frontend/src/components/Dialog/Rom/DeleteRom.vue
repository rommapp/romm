<script setup lang="ts">
import RAvatar from "@/components/Game/Avatar.vue";
import RDialog from "@/components/common/Dialog.vue";
import romApi from "@/services/api/rom";
import storeRoms from "@/stores/roms";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { inject, ref } from "vue";
import { useRouter } from "vue-router";
import { useDisplay, useTheme } from "vuetify";

// Props
const theme = useTheme();
const { mdAndDown, lgAndUp } = useDisplay();
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

// Functions
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
  <r-dialog
    @close="closeDialog"
    v-model="show"
    icon="mdi-delete"
    scroll-content
    :width="lgAndUp ? '900px' : mdAndDown ? '570px' : '85vw'"
  >
    <template #prepend>
      <v-row class="justify-center my-2 px-6">
        <v-list-item>
          <span>Deleting the following</span>
          <span class="text-romm-accent-1 mx-1">{{ roms.length }}</span>
          <span>games. Do you confirm?</span>
        </v-list-item>
      </v-row>
    </template>
    <template #content>
      <v-list>
        <v-list-item v-for="rom in roms" :key="rom.id" class="justify-center">
          <template #prepend>
            <r-avatar
              :src="
                !rom.igdb_id && !rom.moby_id && !rom.has_cover
                  ? `/assets/default/cover/small_${theme.global.name.value}_unmatched.png`
                  : `/assets/romm/resources/${rom.path_cover_s}`
              "
            />
          </template>
          {{ rom.name }} - [<span class="text-romm-accent-1">{{
            rom.file_name
          }}</span
          >]
        </v-list-item>
      </v-list>
    </template>
    <template #append>
      <v-row class="justify-center my-2">
        <v-btn class="bg-terciary" @click="closeDialog" variant="flat"> Cancel </v-btn>
        <v-btn class="text-romm-red ml-2 bg-terciary" variant="flat" @click="deleteRoms">
          Confirm
        </v-btn>
      </v-row>
    </template>
    <template #footer>
      <v-row no-gutters class="align-center">
        <v-checkbox
          v-model="deleteFromFs"
          label="Remove from filesystem"
          class="ml-5"
          hide-details
        />
      </v-row>
    </template>
  </r-dialog>
</template>

<style scoped>
.content-desktop {
  width: 900px;
  max-height: 600px;
}

.content-tablet {
  width: 570px;
  max-height: 600px;
}

.content-mobile {
  width: 85vw;
  max-height: 600px;
}
</style>
