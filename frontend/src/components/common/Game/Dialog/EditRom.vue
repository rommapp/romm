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

const { t } = useI18n();
const { lgAndUp } = useDisplay();
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
const validForm = ref(false);
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
        msg: `Unable to upload manuals: ${
          response?.data?.detail || response?.statusText || message
        }`,
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
      <v-form v-model="validForm">
        <v-row class="d-flex justify-center" no-gutters>
          <v-col class="pa-4" cols="auto">
            <game-card
              width="240"
              :rom="rom"
              :src="imagePreviewUrl"
              disableViewTransition
              :showPlatformIcon="false"
              :showActionBar="false"
            >
              <template #append-inner-right>
                <v-btn-group divided density="compact" rounded="0">
                  <v-btn
                    :disabled="
                      !heartbeat.value.METADATA_SOURCES?.STEAMGRIDDB_API_ENABLED
                    "
                    size="small"
                    class="translucent"
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
                    class="translucent"
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
                    class="translucent"
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
          <v-col class="pa-4">
            <v-text-field
              v-model="rom.name"
              :rules="[(value: string) => !!value || t('common.required')]"
              :label="t('common.name')"
              variant="outlined"
              @keyup.enter="updateRom"
              class="my-2"
            />
            <v-text-field
              v-model="rom.fs_name"
              :rules="[(value: string) => !!value || t('common.required')]"
              :label="rom.multi ? t('rom.folder-name') : t('rom.filename')"
              variant="outlined"
              @keyup.enter="updateRom"
              class="my-2"
            >
              <template #details>
                <v-label class="text-caption text-wrap">
                  <v-icon size="small" class="text-primary mr-2">
                    mdi-folder-file-outline
                  </v-icon>
                  <span>
                    /romm/library/{{ rom.fs_path }}/{{ rom.fs_name }}
                  </span>
                </v-label>
              </template>
            </v-text-field>
            <v-textarea
              v-model="rom.summary"
              :label="t('rom.summary')"
              variant="outlined"
              class="my-2"
            />
            <v-chip
              :variant="rom.has_manual ? 'flat' : 'tonal'"
              label
              size="large"
              class="bg-toplayer px-0"
            >
              <span
                class="ml-4"
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
                  class="file-input"
                  @change="uploadManuals"
                />
              </v-btn>
            </v-chip>
            <div v-if="rom.has_manual">
              <v-label class="text-caption text-wrap">
                <v-icon size="small" class="text-primary mr-2">
                  mdi-folder-file-outline
                </v-icon>
                <span> /romm/resources/{{ rom.path_manual }} </span>
              </v-label>
            </div>
            <div class="mt-6">
              <v-btn
                :disabled="rom.is_unidentified"
                :class="{
                  'text-romm-red bg-toplayer': !rom.is_unidentified,
                }"
                variant="flat"
                @click="unmatchRom"
              >
                {{ t("rom.unmatch") }}
              </v-btn>
            </div>
          </v-col>
        </v-row>
      </v-form>
    </template>
    <template #append>
      <v-divider />
      <v-row class="justify-center pa-2" no-gutters>
        <v-btn-group divided density="compact">
          <v-btn class="bg-toplayer" @click="closeDialog">
            {{ t("common.cancel") }}
          </v-btn>
          <v-btn
            :variant="!validForm ? 'plain' : 'flat'"
            :disabled="!validForm"
            class="text-romm-green bg-toplayer"
            @click="updateRom"
          >
            {{ t("common.apply") }}
          </v-btn>
        </v-btn-group>
      </v-row>
    </template>
  </r-dialog>
</template>
