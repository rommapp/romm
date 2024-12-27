<script setup lang="ts">
import GameCard from "@/components/common/Game/Card/Base.vue";
import RDialog from "@/components/common/RDialog.vue";
import romApi, { type UpdateRom } from "@/services/api/rom";
import storeGalleryView from "@/stores/galleryView";
import storeHeartbeat from "@/stores/heartbeat";
import storePlatforms from "@/stores/platforms";
import storeRoms, { type SimpleRom } from "@/stores/roms";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { computed, inject, ref } from "vue";
import { useRoute } from "vue-router";
import { useDisplay, useTheme } from "vuetify";
import { useI18n } from "vue-i18n";

// Props
const { t } = useI18n();
const theme = useTheme();
const { lgAndUp, mdAndUp, smAndDown } = useDisplay();
const heartbeat = storeHeartbeat();
const route = useRoute();
const show = ref(false);
const rom = ref<UpdateRom>();
const romsStore = storeRoms();
const imagePreviewUrl = ref<string | undefined>("");
const removeCover = ref(false);
const platfotmsStore = storePlatforms();
const galleryViewStore = storeGalleryView();
const emitter = inject<Emitter<Events>>("emitter");
emitter?.on("showEditRomDialog", (romToEdit: UpdateRom | undefined) => {
  show.value = true;
  rom.value = romToEdit;
  removeCover.value = false;
});
emitter?.on("updateUrlCover", (url_cover) => {
  if (!rom.value) return;
  rom.value.url_cover = url_cover;
  setArtwork(url_cover);
});
const computedAspectRatio = computed(() => {
  const ratio = rom.value?.platform_id
    ? platfotmsStore.getAspectRatio(rom.value?.platform_id)
    : galleryViewStore.defaultAspectRatioCover;
  return parseFloat(ratio.toString());
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
    setArtwork(reader.result?.toString() || "");
  };
  if (input.files[0]) {
    reader.readAsDataURL(input.files[0]);
  }
}

function setArtwork(imageUrl: string) {
  if (!imageUrl) return;
  imagePreviewUrl.value = imageUrl;
  removeCover.value = false;
}

async function removeArtwork() {
  imagePreviewUrl.value = `/assets/default/cover/big_${theme.global.name.value}_missing_cover.png`;
  removeCover.value = true;
}

const noMetadataMatch = computed(() => {
  return !rom.value?.igdb_id && !rom.value?.moby_id && !rom.value?.sgdb_id;
});

async function handleRomUpdate(
  options: {
    rom: UpdateRom;
    renameAsSource?: boolean;
    removeCover?: boolean;
    unmatch?: boolean;
  },
  successMessage: string,
) {
  show.value = false;
  emitter?.emit("showLoadingDialog", { loading: true, scrim: true });

  await romApi
    .updateRom(options)
    .then(({ data }) => {
      emitter?.emit("snackbarShow", {
        msg: successMessage,
        icon: "mdi-check-bold",
        color: "green",
      });
      romsStore.update(data as SimpleRom);
      if (route.name == "rom") {
        romsStore.currentRom = data;
      }
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
      closeDialog();
    });
}

async function unmatchRom() {
  if (!rom.value) return;
  await handleRomUpdate(
    { rom: rom.value, unmatch: true },
    "Rom unmatched successfully",
  );
}

async function updateRom() {
  if (!rom.value?.file_name) {
    emitter?.emit("snackbarShow", {
      msg: "Cannot save: file name is required",
      icon: "mdi-close-circle",
      color: "red",
    });
    return;
  }

  await handleRomUpdate(
    { rom: rom.value, removeCover: removeCover.value },
    "Rom updated successfully!",
  );
}

function closeDialog() {
  show.value = false;
  imagePreviewUrl.value = "";
  rom.value = undefined;
}
</script>

<template>
  <r-dialog
    v-if="rom"
    @close="closeDialog"
    v-model="show"
    icon="mdi-pencil-box"
    scroll-content
    :width="lgAndUp ? '65vw' : '95vw'"
  >
    <template #content>
      <v-row class="align-center pa-2" no-gutters>
        <v-col cols="12" md="8" xl="9">
          <v-row class="px-2" no-gutters>
            <v-col>
              <v-text-field
                v-model="rom.name"
                class="py-2"
                :label="t('common.name')"
                variant="outlined"
                required
                hide-details
                @keyup.enter="updateRom()"
              />
            </v-col>
          </v-row>
          <v-row class="px-2" no-gutters>
            <v-col>
              <v-text-field
                v-model="rom.file_name"
                class="py-2"
                :rules="[(value: string) => !!value]"
                :label="rom.multi ? t('rom.foldername') : t('rom.filename')"
                variant="outlined"
                required
                @keyup.enter="updateRom()"
              >
                <template #details>
                  <v-label class="text-caption text-wrap">
                    <v-icon size="small" class="mr-2 text-romm-accent-1">
                      mdi-folder-file-outline
                    </v-icon>
                    <span>
                      /romm/library/{{ rom.file_path }}/{{ rom.file_name }}
                    </span>
                  </v-label>
                </template>
              </v-text-field>
            </v-col>
          </v-row>
          <v-row class="px-2" no-gutters>
            <v-col>
              <v-textarea
                v-model="rom.summary"
                class="py-2"
                :label="t('rom.summary')"
                variant="outlined"
                required
                hide-details
                @keyup.enter="updateRom"
              />
            </v-col>
          </v-row>
        </v-col>
        <v-col cols="12" md="4" xl="3">
          <v-row
            class="justify-center"
            :class="{ 'mt-4': smAndDown }"
            no-gutters
          >
            <v-col style="max-width: 240px">
              <game-card :rom="rom" :src="imagePreviewUrl">
                <template #append-inner-right>
                  <v-btn-group rounded="0" divided density="compact">
                    <v-btn
                      :disabled="
                        !heartbeat.value.METADATA_SOURCES?.STEAMGRIDDB_ENABLED
                      "
                      size="small"
                      class="translucent-dark"
                      @click="
                        emitter?.emit('showSearchCoverDialog', {
                          term: rom.name as string,
                          aspectRatio: computedAspectRatio,
                        })
                      "
                    >
                      <v-icon size="large">mdi-image-search-outline</v-icon>
                    </v-btn>
                    <v-btn
                      size="small"
                      class="translucent-dark"
                      @click="triggerFileInput"
                    >
                      <v-icon size="large">mdi-pencil</v-icon>
                      <v-file-input
                        id="file-input"
                        v-model="rom.artwork"
                        accept="image/*"
                        hide-details
                        class="file-input"
                        @change="previewImage"
                      />
                    </v-btn>
                    <v-btn
                      size="small"
                      class="translucent-dark"
                      @click="removeArtwork"
                    >
                      <v-icon size="large" class="text-romm-red"
                        >mdi-delete</v-icon
                      >
                    </v-btn>
                  </v-btn-group>
                </template>
              </game-card>
            </v-col>
          </v-row>
        </v-col>
      </v-row>
      <v-row class="justify-space-between px-4 py-2 mt-1" no-gutters>
        <v-btn
          :disabled="noMetadataMatch"
          :class="` ${noMetadataMatch ? '' : 'bg-terciary text-romm-red'}`"
          variant="flat"
          @click="unmatchRom"
        >
          {{ t("rom.unmatch-rom") }}
        </v-btn>
        <v-btn-group divided density="compact">
          <v-btn class="bg-terciary" @click="closeDialog">
            {{ t("common.cancel") }}
          </v-btn>
          <v-btn class="text-romm-green bg-terciary" @click="updateRom">
            {{ t("common.apply") }}
          </v-btn>
        </v-btn-group>
      </v-row>
    </template>
  </r-dialog>
</template>
