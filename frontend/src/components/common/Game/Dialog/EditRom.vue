<script setup lang="ts">
import GameCard from "@/components/common/Game/Card/Base.vue";
import RDialog from "@/components/common/RDialog.vue";
import romApi, { type UpdateRom } from "@/services/api/rom";
import storeRoms from "@/stores/roms";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { inject, ref } from "vue";
import { useDisplay, useTheme } from "vuetify";

// Props
const theme = useTheme();
const { smAndDown, lgAndUp } = useDisplay();
const show = ref(false);
const rom = ref<UpdateRom>();
const romsStore = storeRoms();
const imagePreviewUrl = ref<string | undefined>("");
const removeCover = ref(false);
const fileNameInputRules = {
  required: (value: string) => !!value || "Required",
  newFileName: (value: string) => !value.includes("/") || "Invalid characters",
};
const emitter = inject<Emitter<Events>>("emitter");
emitter?.on("showEditRomDialog", (romToEdit: UpdateRom | undefined) => {
  show.value = true;
  rom.value = romToEdit;
});

// Functions
function triggerFileInput() {
  const fileInput = document.getElementById("file-input");
  fileInput?.click();
}

function previewImage(event: Event) {
  const input = event.target as HTMLInputElement;
  if (!input.files) return;

  const reader = new FileReader();
  reader.onload = () => {
    imagePreviewUrl.value = reader.result?.toString();
  };
  if (input.files[0]) {
    reader.readAsDataURL(input.files[0]);
  }
}

async function removeArtwork() {
  imagePreviewUrl.value = `/assets/default/cover/big_${theme.global.name.value}_missing_cover.png`;
  removeCover.value = true;
}

async function updateRom() {
  if (!rom.value) return;

  if (rom.value.file_name.includes("/")) {
    emitter?.emit("snackbarShow", {
      msg: "Couldn't edit rom: invalid file name characters",
      icon: "mdi-close-circle",
      color: "red",
    });
    return;
  } else if (!rom.value.file_name) {
    emitter?.emit("snackbarShow", {
      msg: "Couldn't edit rom: file name required",
      icon: "mdi-close-circle",
      color: "red",
    });
    return;
  }

  show.value = false;
  emitter?.emit("showLoadingDialog", { loading: true, scrim: true });

  await romApi
    .updateRom({ rom: rom.value, removeCover: removeCover.value })
    .then(({ data }) => {
      emitter?.emit("snackbarShow", {
        msg: "Rom updated successfully!",
        icon: "mdi-check-bold",
        color: "green",
      });
      romsStore.update(data);
      emitter?.emit("refreshView", null);
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
  imagePreviewUrl.value = "";
}
</script>

<template>
  <r-dialog
    v-if="rom"
    @close="closeDialog"
    v-model="show"
    icon="mdi-pencil-box"
    :width="lgAndUp ? '65vw' : '95vw'"
  >
    <template #content>
      <v-row class="align-center pa-2" no-gutters>
        <v-col cols="12" md="8" lg="8" xl="9">
          <v-row class="pa-2" no-gutters>
            <v-col>
              <v-text-field
                v-model="rom.name"
                class="py-2"
                label="Name"
                variant="outlined"
                required
                hide-details
                @keyup.enter="updateRom()"
              />
            </v-col>
          </v-row>
          <v-row class="pa-2" no-gutters>
            <v-col>
              <v-text-field
                v-model="rom.file_name"
                class="py-2"
                :rules="[
                  fileNameInputRules.newFileName,
                  fileNameInputRules.required,
                ]"
                label="File name"
                variant="outlined"
                required
                hide-details
                @keyup.enter="updateRom()"
              />
            </v-col>
          </v-row>
          <v-row class="pa-2" no-gutters>
            <v-col>
              <v-textarea
                v-model="rom.summary"
                class="py-2"
                label="Summary"
                variant="outlined"
                required
                hide-details
                @keyup.enter="updateRom()"
              />
            </v-col>
          </v-row>
        </v-col>
        <v-col>
          <v-row class="pa-2 justify-center" no-gutters>
            <v-col class="cover">
              <game-card :rom="rom" :src="imagePreviewUrl">
                <template #append-inner>
                  <v-chip-group class="pa-0">
                    <v-chip
                      class="translucent-dark"
                      :size="smAndDown ? 'large' : 'small'"
                      @click="triggerFileInput"
                      label
                    >
                      <v-icon>mdi-pencil</v-icon>
                      <v-file-input
                        id="file-input"
                        v-model="rom.artwork"
                        accept="image/*"
                        hide-details
                        class="file-input"
                        @change="previewImage"
                      />
                    </v-chip>
                    <v-chip
                      class="translucent-dark"
                      :size="smAndDown ? 'large' : 'small'"
                      @click="removeArtwork"
                      label
                    >
                      <v-icon class="text-romm-red"> mdi-delete </v-icon>
                    </v-chip>
                  </v-chip-group>
                </template>
              </game-card>
            </v-col>
          </v-row>
        </v-col>
      </v-row>
    </template>
    <template #append>
      <v-row class="justify-center mb-2" no-gutters>
        <v-btn-group divided density="compact">
          <v-btn class="bg-terciary" @click="closeDialog" >
            Cancel
          </v-btn>
          <v-btn
            class="text-romm-green bg-terciary"
            @click="updateRom"
          >
            Apply
          </v-btn>
        </v-btn-group>
      </v-row>
    </template>
  </r-dialog>
</template>
<style scoped>
.cover {
  min-width: 240px;
  min-height: 330px;
  max-width: 240px;
  max-height: 330px;
}
</style>