<script setup lang="ts">
import Cover from "@/components/Details/Cover.vue";
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
emitter?.on("showEditRomDialog", (romToEdit) => {
  show.value = true;
  rom.value = romToEdit;
});

// Functions
function triggerFileInput() {
  const fileInput = document.getElementById("file-input");
  fileInput?.click();
}

function previewImage(event: { target: { files: any[] } }) {
  const file = event.target.files[0];
  const reader = new FileReader();
  reader.onload = () => {
    imagePreviewUrl.value = reader.result?.toString();
  };
  if (file) {
    reader.readAsDataURL(file);
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
    :modelValue="show"
    scroll-strategy="none"
    width="auto"
    :scrim="true"
    @click:outside="closeDialog"
    @keydown.esc="closeDialog"
    no-click-animation
    persistent
    v-if="rom"
  >
    <v-card
      rounded="0"
      :class="{
        'edit-content': lgAndUp,
        'edit-content-tablet': mdAndDown,
        'edit-content-mobile': xs,
      }"
    >
      <v-toolbar density="compact" class="bg-terciary">
        <v-row class="align-center" no-gutters>
          <v-col cols="9" xs="9" sm="10" md="10" lg="11">
            <v-icon icon="mdi-pencil-box" class="ml-5" />
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
        <v-row class="align-center" no-gutters>
          <v-col cols="12" md="8" lg="9">
            <v-text-field
              class="py-2"
              :class="{ 'pr-4': lgAndUp }"
              @keyup.enter="updateRom()"
              v-model="rom.name"
              label="Name"
              variant="outlined"
              required
              hide-details
            />
            <v-text-field
              class="py-2"
              :class="{ 'pr-4': lgAndUp }"
              @keyup.enter="updateRom()"
              v-model="rom.file_name"
              :rules="[
                fileNameInputRules.newFileName,
                fileNameInputRules.required,
              ]"
              label="File name"
              variant="outlined"
              required
              hide-details
            />
            <v-textarea
              class="py-2"
              :class="{ 'pr-4': lgAndUp }"
              @keyup.enter="updateRom()"
              v-model="rom.summary"
              label="Summary"
              variant="outlined"
              required
              hide-details
            />
          </v-col>
          <v-col cols="12" md="4" lg="3">
            <cover
              :class="{ 'mx-16': smAndDown, 'ml-2': md, 'my-4': smAndDown }"
              :romId="rom.id"
              :src="
                imagePreviewUrl
                  ? imagePreviewUrl
                  : !rom.igdb_id && !rom.has_cover
                  ? `/assets/default/cover/big_${theme.global.name.value}_unmatched.png`
                  : !rom.has_cover
                  ? `/assets/default/cover/big_${theme.global.name.value}_missing_cover.png`
                  : `/assets/romm/resources/${rom.path_cover_l}`
              "
              :lazy-src="
                imagePreviewUrl
                  ? imagePreviewUrl
                  : !rom.igdb_id && !rom.has_cover
                  ? `/assets/default/cover/small_${theme.global.name.value}_unmatched.png`
                  : !rom.has_cover
                  ? `/assets/default/cover/small_${theme.global.name.value}_missing_cover.png`
                  : `/assets/romm/resources/${rom.path_cover_s}`
              "
            >
              <template v-slot:editable>
                <v-chip-group class="position-absolute edit-cover pa-0">
                  <v-chip
                    class="translucent"
                    size="small"
                    @click="triggerFileInput"
                    label
                    ><v-icon>mdi-pencil</v-icon>
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
                    class="translucent"
                    size="small"
                    @click="removeArtwork"
                    label
                    ><v-icon class="text-red">mdi-delete</v-icon></v-chip
                  >
                </v-chip-group>
              </template>
            </cover>
          </v-col>
        </v-row>
        <v-row class="justify-center pa-2" no-gutters>
          <v-btn @click="closeDialog" class="bg-terciary">Cancel</v-btn>
          <v-btn @click="updateRom()" class="text-romm-green ml-5 bg-terciary"
            >Apply</v-btn
          >
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
.edit-cover {
  bottom: -0.1rem;
  right: -0.3rem;
}
.file-input {
  display: none;
}
.translucent {
  background: rgba(0, 0, 0, 0.35);
  backdrop-filter: blur(10px);
}
</style>
