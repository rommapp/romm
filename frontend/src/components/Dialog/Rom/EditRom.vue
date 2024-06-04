<script setup lang="ts">
import GameCard from "@/components/Game/Card/Base.vue";
import romApi, { type UpdateRom } from "@/services/api/rom";
import storeRoms from "@/stores/roms";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { inject, ref } from "vue";
import { useDisplay, useTheme } from "vuetify";

// Props
const theme = useTheme();
const { xs, mdAndDown, smAndDown, md, lgAndUp } = useDisplay();
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
  <v-dialog
    v-if="rom"
    :model-value="show"
    scroll-strategy="none"
    width="auto"
    :scrim="true"
    no-click-animation
    persistent
    @click:outside="closeDialog"
    @keydown.esc="closeDialog"
  >
    <v-card
      rounded="0"
      :class="{
        'edit-content': lgAndUp,
        'edit-content-tablet': mdAndDown,
        'edit-content-mobile': xs,
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
            sm="10"
            lg="11"
          >
            <v-icon
              icon="mdi-pencil-box"
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
        
        
      />

      <v-card-text>
        <v-row class="align-center" no-gutters>
          <v-col cols="12" lg="9">
            <v-text-field
              v-model="rom.name"
              class="py-2"
              :class="{ 'pr-4': lgAndUp }"
              label="Name"
              variant="outlined"
              required
              hide-details
              @keyup.enter="updateRom()"
            />
            <v-text-field
              v-model="rom.file_name"
              class="py-2"
              :class="{ 'pr-4': lgAndUp }"
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
            <v-textarea
              v-model="rom.summary"
              class="py-2"
              :class="{ 'pr-4': lgAndUp }"
              label="Summary"
              variant="outlined"
              required
              hide-details
              @keyup.enter="updateRom()"
            />
          </v-col>
          <v-col
            cols="12"
            lg="3"
            :class="{
              'my-4': mdAndDown,
              'px-10': mdAndDown,
            }"
          >
            <game-card :rom="rom" :src="imagePreviewUrl">
              <template #append-inner>
                <v-chip-group class="pa-0">
                  <v-chip
                    class="translucent-dark"
                    :size="mdAndDown ? 'large' : 'small'"
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
                    :size="mdAndDown ? 'large' : 'small'"
                    @click="removeArtwork"
                    label
                  >
                    <v-icon class="text-red">
                      mdi-delete
                    </v-icon>
                  </v-chip>
                </v-chip-group>
              </template>
            </game-card>
          </v-col>
        </v-row>
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
            class="text-romm-green ml-5 bg-terciary"
            @click="updateRom()"
          >
            Apply
          </v-btn>
        </v-row>
      </v-card-text>
    </v-card>
  </v-dialog>
</template>

<style scoped>
.edit-content {
  width: 900px;
}
.edit-content-tablet {
  width: 620px;
}
.edit-content-mobile {
  width: 85vw;
}
</style>
