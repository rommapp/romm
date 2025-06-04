<script setup lang="ts">
import GameCard from "@/components/common/Game/Card/Base.vue";
import RDialog from "@/components/common/RDialog.vue";
import romApi, { type UpdateRom } from "@/services/api/rom";
import storeGalleryView from "@/stores/galleryView";
import storeHeartbeat from "@/stores/heartbeat";
import storePlatforms from "@/stores/platforms";
import storeRoms, { type SimpleRom } from "@/stores/roms";
import storeUpload from "@/stores/upload";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { computed, inject, ref } from "vue";
import { useRoute } from "vue-router";
import { useDisplay } from "vuetify";
import { useI18n } from "vue-i18n";
import { getMissingCoverImage } from "@/utils/covers";

// Props
const { t } = useI18n();
const { lgAndUp, smAndDown } = useDisplay();
const heartbeat = storeHeartbeat();
const route = useRoute();
const show = ref(false);
const rom = ref<UpdateRom>();
const romsStore = storeRoms();
const imagePreviewUrl = ref<string | undefined>("");
const removeCover = ref(false);
const manualFiles = ref<File[]>([]);
const platfotmsStore = storePlatforms();
const galleryViewStore = storeGalleryView();
const uploadStore = storeUpload();
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
const missingCoverImage = computed(() =>
  getMissingCoverImage(rom.value?.name || rom.value?.fs_name || ""),
);

// Functions
function triggerFileInput(id: string) {
  const fileInput = document.getElementById(id);
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
  imagePreviewUrl.value = missingCoverImage.value;
  removeCover.value = true;
}

const noMetadataMatch = computed(() => {
  return !rom.value?.igdb_id && !rom.value?.moby_id && !rom.value?.ss_id;
});

async function handleRomUpdate(
  options: {
    rom: UpdateRom;
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

async function uploadManuals() {
  if (!rom.value) return;

  await romApi
    .uploadManuals({
      romId: rom.value.id,
      filesToUpload: manualFiles.value,
    })
    .then((responses: PromiseSettledResult<unknown>[]) => {
      const successfulUploads = responses.filter(
        (d) => d.status == "fulfilled",
      );
      const failedUploads = responses.filter((d) => d.status == "rejected");

      if (failedUploads.length == 0) {
        uploadStore.reset();
      }

      if (successfulUploads.length == 0) {
        return emitter?.emit("snackbarShow", {
          msg: `All manuals skipped, nothing to upload.`,
          icon: "mdi-close-circle",
          color: "orange",
          timeout: 5000,
        });
      }

      emitter?.emit("snackbarShow", {
        msg: `${successfulUploads.length} manuals uploaded successfully (and ${failedUploads.length} skipped/failed).`,
        icon: "mdi-check-bold",
        color: "green",
        timeout: 3000,
      });
    })
    .catch(({ response, message }) => {
      emitter?.emit("snackbarShow", {
        msg: `Unable to upload manuals: ${response?.data?.detail || response?.statusText || message}`,
        icon: "mdi-close-circle",
        color: "red",
        timeout: 4000,
      });
    });
  manualFiles.value = [];
}

async function unmatchRom() {
  if (!rom.value) return;
  await handleRomUpdate(
    { rom: rom.value, unmatch: true },
    "Rom unmatched successfully",
  );
}

async function updateRom() {
  if (!rom.value?.fs_name) {
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
                v-model="rom.fs_name"
                class="py-2"
                :rules="[(value: string) => !!value]"
                :label="rom.multi ? t('rom.foldername') : t('rom.filename')"
                variant="outlined"
                required
                @keyup.enter="updateRom()"
              >
                <template #details>
                  <v-label class="text-caption text-wrap">
                    <v-icon size="small" class="mr-2 text-primary">
                      mdi-folder-file-outline
                    </v-icon>
                    <span>
                      /romm/library/{{ rom.fs_path }}/{{ rom.fs_name }}
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
          <v-row class="px-2 mt-2" no-gutters>
            <v-col>
              <v-chip
                :variant="rom.has_manual ? 'flat' : 'tonal'"
                label
                size="large"
                class="pr-0 bg-toplayer"
              >
                <span
                  :class="{
                    'text-romm-red': !rom.has_manual,
                    'text-romm-green': rom.has_manual,
                  }"
                  >{{ t("rom.manual")
                  }}<v-icon class="ml-1">{{
                    rom.has_manual ? "mdi-check" : "mdi-close"
                  }}</v-icon></span
                >
                <v-btn
                  @click="triggerFileInput('manual-file-input')"
                  class="bg-toplayer ml-3"
                  icon="mdi-cloud-upload-outline"
                  rounded="0"
                  size="small"
                >
                  <v-icon size="large">mdi-cloud-upload-outline</v-icon>
                  <v-file-input
                    id="manual-file-input"
                    v-model="manualFiles"
                    accept="application/pdf"
                    hide-details
                    multiple
                    required
                    class="file-input"
                    @change="uploadManuals"
                  />
                </v-btn>
              </v-chip>
              <div v-if="rom.has_manual" class="mt-1">
                <v-label class="text-caption text-wrap">
                  <v-icon size="small" class="mr-2 text-primary">
                    mdi-folder-file-outline
                  </v-icon>
                  <span> /romm/resources/{{ rom.path_manual }} </span>
                </v-label>
              </div>
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
              <game-card
                :rom="rom"
                :src="imagePreviewUrl"
                disableViewTransition
              >
                <template #append-inner-right>
                  <v-btn-group divided density="compact" rounded="0">
                    <v-btn
                      :disabled="
                        !heartbeat.value.METADATA_SOURCES
                          ?.STEAMGRIDDB_API_ENABLED
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
                      @click="triggerFileInput('cover-file-input')"
                    >
                      <v-icon size="large">mdi-pencil</v-icon>
                      <v-file-input
                        id="cover-file-input"
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
          :class="` ${noMetadataMatch ? '' : 'bg-toplayer text-romm-red'}`"
          variant="flat"
          @click="unmatchRom"
        >
          {{ t("rom.unmatch-rom") }}
        </v-btn>
        <v-btn-group divided density="compact">
          <v-btn class="bg-toplayer" @click="closeDialog">
            {{ t("common.cancel") }}
          </v-btn>
          <v-btn class="text-romm-green bg-toplayer" @click="updateRom">
            {{ t("common.apply") }}
          </v-btn>
        </v-btn-group>
      </v-row>
    </template>
  </r-dialog>
</template>
