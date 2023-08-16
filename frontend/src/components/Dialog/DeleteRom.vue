<script setup>
import { ref, inject } from "vue";
import { useRouter } from "vue-router";
import { useDisplay } from "vuetify";
import { deleteRomApi } from "@/services/api.js";

const { xs, mdAndDown, lgAndUp } = useDisplay();
const router = useRouter();
const show = ref(false);
const rom = ref();
const deleteFromFs = ref(false);

const emitter = inject("emitter");
emitter.on("showDeleteDialog", (romToDelete) => {
  rom.value = romToDelete;
  show.value = true;
});

async function deleteRom() {
  await deleteRomApi(rom.value, deleteFromFs.value)
    .then((response) => {
      emitter.emit("snackbarShow", {
        msg: response.data.msg,
        icon: "mdi-check-bold",
        color: "green",
      });
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
    params: { platform: rom.value.p_slug },
  });
  emitter.emit("refreshGallery");
  emitter.emit("refreshPlatforms");
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
          <span class="mr-1">Deleting</span>
          <span class="text-rommAccent1">{{ rom.file_name }}</span
          >.<span class="ml-1">Do you confirm?</span>
        </v-row>
        <v-row class="justify-center pa-2" no-gutters>
          <v-btn @click="show = false" class="bg-terciary">Cancel</v-btn>
          <v-btn @click="deleteRom()" class="text-rommRed bg-terciary ml-5"
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
}

.delete-content-tablet {
  width: 570px;
}

.delete-content-mobile {
  width: 85vw;
}
</style>
