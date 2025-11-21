<script setup lang="ts">
import type { Emitter } from "mitt";
import { computed, inject, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute } from "vue-router";
import { useDisplay } from "vuetify";
import GameCard from "@/components/common/Game/Card/Base.vue";
import RDialog from "@/components/common/RDialog.vue";
import romApi, { type UpdateRom } from "@/services/api/rom";
import storeHeartbeat from "@/stores/heartbeat";
import storeRoms, { type SimpleRom } from "@/stores/roms";
import storeUpload from "@/stores/upload";
import type { Events } from "@/types/emitter";
import { getMissingCoverImage } from "@/utils/covers";
import MetadataIdSection from "./EditRom/MetadataIdSection.vue";
import MetadataSections from "./EditRom/MetadataSections.vue";

const { t } = useI18n();
const { lgAndUp } = useDisplay();
const heartbeat = storeHeartbeat();
const route = useRoute();
const show = ref(false);
const rom = ref<UpdateRom | null>(null);
const romsStore = storeRoms();
const imagePreviewUrl = ref<string | undefined>("");
const removeCover = ref(false);
const manualFiles = ref<File[]>([]);
const uploadStore = storeUpload();
const validForm = ref(false);
const showConfirmDeleteManual = ref(false);
const emitter = inject<Emitter<Events>>("emitter");

emitter?.on("showEditRomDialog", (romToEdit: SimpleRom) => {
  show.value = true;
  rom.value = romToEdit;
  removeCover.value = false;
});

emitter?.on("updateUrlCover", (url_cover) => {
  setArtwork(url_cover);
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

function setArtwork(coverUrl: string) {
  if (!coverUrl || !rom.value) return;
  rom.value.url_cover = coverUrl;
  imagePreviewUrl.value = coverUrl;
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
      console.error(error);
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
          msg: t("rom.manuals-upload-skipped"),
          icon: "mdi-close-circle",
          color: "orange",
          timeout: 5000,
        });
      }

      emitter?.emit("snackbarShow", {
        msg: t("rom.manuals-upload-success", {
          count: successfulUploads.length,
          failed: failedUploads.length,
        }),
        icon: "mdi-check-bold",
        color: "green",
        timeout: 3000,
      });
    })
    .catch(({ response, message }) => {
      emitter?.emit("snackbarShow", {
        msg: t("rom.manuals-upload-failed", {
          error: response?.data?.detail || response?.statusText || message,
        }),
        icon: "mdi-close-circle",
        color: "red",
        timeout: 4000,
      });
    });
  manualFiles.value = [];
}

function confirmRemoveManual() {
  showConfirmDeleteManual.value = true;
}

async function removeManual() {
  if (!rom.value) return;
  showConfirmDeleteManual.value = false;

  try {
    await romApi.removeManual({ romId: rom.value.id });
    rom.value.has_manual = false;
    rom.value.url_manual = "";
    rom.value.path_manual = "";

    emitter?.emit("snackbarShow", {
      msg: t("rom.manual-removed"),
      icon: "mdi-check-bold",
      color: "green",
    });
  } catch (error: any) {
    emitter?.emit("snackbarShow", {
      msg: t("rom.manual-remove-failed", {
        error: error.response?.data?.detail || error.message,
      }),
      icon: "mdi-close-circle",
      color: "red",
    });
  }
}

async function unmatchRom() {
  if (!rom.value) return;
  await handleRomUpdate(
    { rom: rom.value, unmatch: true },
    t("rom.unmatch-success"),
  );
}

async function updateRom() {
  if (!rom.value?.fs_name) {
    emitter?.emit("snackbarShow", {
      msg: t("rom.filename-required"),
      icon: "mdi-close-circle",
      color: "red",
    });
    return;
  }

  await handleRomUpdate(
    { rom: rom.value, removeCover: removeCover.value },
    t("rom.update-success"),
  );
}

function closeDialog() {
  show.value = false;
  rom.value = null;
  imagePreviewUrl.value = "";
  showConfirmDeleteManual.value = false;
}

function handleRomUpdateFromMetadata(updatedRom: UpdateRom) {
  rom.value = updatedRom;
}
</script>

<template>
  <RDialog
    v-if="rom"
    v-model="show"
    icon="mdi-pencil-box"
    scroll-content
    :width="lgAndUp ? '65vw' : '95vw'"
    @close="closeDialog"
  >
    <template #content>
      <v-form v-model="validForm">
        <v-row class="d-flex justify-center" no-gutters>
          <v-col class="pa-4" cols="auto">
            <GameCard
              width="240"
              :rom="rom"
              :cover-src="imagePreviewUrl"
              disable-view-transition
              :show-platform-icon="false"
              :show-action-bar="false"
              force-boxart="cover_path"
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
                        term: rom.name || rom.fs_name,
                        platformId: rom.platform_id,
                      })
                    "
                  >
                    <v-icon size="large"> mdi-image-search-outline </v-icon>
                  </v-btn>
                  <v-btn
                    size="small"
                    class="translucent"
                    @click="triggerFileInput('cover-file-input')"
                  >
                    <v-icon size="large"> mdi-pencil </v-icon>
                    <v-file-input
                      hide-details
                      id="cover-file-input"
                      v-model="rom.artwork"
                      accept="image/*"
                      class="file-input"
                      @change="previewImage"
                    />
                  </v-btn>
                  <v-btn
                    size="small"
                    class="translucent"
                    @click="removeArtwork"
                  >
                    <v-icon size="large" class="text-romm-red">
                      mdi-delete
                    </v-icon>
                  </v-btn>
                </v-btn-group>
              </template>
            </GameCard>
          </v-col>
          <v-col class="pa-4">
            <v-text-field
              hide-details
              v-model="rom.name"
              :rules="[(value: string) => !!value || t('common.required')]"
              :label="t('common.name')"
              variant="outlined"
              class="my-4"
            />
            <v-text-field
              hide-details
              v-model="rom.fs_name"
              :rules="[(value: string) => !!value || t('common.required')]"
              :label="
                rom.has_multiple_files
                  ? t('rom.folder-name')
                  : t('rom.filename')
              "
              variant="outlined"
              class="my-4"
            >
              <template #details>
                <v-label class="text-caption text-wrap mt-1">
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
              hide-details
              v-model="rom.summary"
              :label="t('rom.summary')"
              variant="outlined"
              class="my-4"
            />

            <div class="d-flex justify-space-between">
              <v-chip
                :variant="rom.has_manual ? 'flat' : 'tonal'"
                label
                class="bg-toplayer px-0"
              >
                <span
                  class="ml-4 flex items-center"
                  :class="{
                    'text-romm-red': !rom.has_manual,
                    'text-romm-green': rom.has_manual,
                  }"
                >
                  {{ t("rom.manual") }}
                  <v-icon class="ml-1">
                    {{ rom.has_manual ? "mdi-check" : "mdi-close" }}
                  </v-icon>
                </span>
                <v-btn
                  class="bg-toplayer ml-3"
                  icon="mdi-cloud-upload-outline"
                  rounded="0"
                  size="small"
                  @click="triggerFileInput('manual-file-input')"
                >
                  <v-icon size="large"> mdi-cloud-upload-outline </v-icon>
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
                <v-btn
                  v-if="rom.has_manual"
                  size="small"
                  class="bg-toplayer text-romm-red"
                  icon="mdi-delete"
                  rounded="0"
                  @click="confirmRemoveManual"
                />
              </v-chip>
              <v-btn
                :disabled="rom.is_unidentified"
                class="ml-2"
                :class="{
                  'text-romm-red bg-toplayer': !rom.is_unidentified,
                }"
                variant="flat"
                @click="unmatchRom"
              >
                {{ t("rom.unmatch") }}
              </v-btn>
            </div>
            <div v-if="rom.has_manual">
              <v-label class="text-caption text-wrap">
                <v-icon size="small" class="text-primary mr-2">
                  mdi-folder-file-outline
                </v-icon>
                <span> /romm/resources/{{ rom.path_manual }} </span>
              </v-label>
            </div>
          </v-col>
        </v-row>
        <v-expansion-panels class="mt-6">
          <MetadataIdSection
            :rom="rom"
            @update:rom="handleRomUpdateFromMetadata"
          />
          <MetadataSections
            :rom="rom"
            @update:rom="handleRomUpdateFromMetadata"
          />
        </v-expansion-panels>
      </v-form>
    </template>
    <template #footer>
      <v-row class="justify-center" no-gutters>
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
  </RDialog>

  <RDialog
    v-model="showConfirmDeleteManual"
    icon="mdi-alert-circle"
    :width="lgAndUp ? '400px' : '90vw'"
  >
    <template #content>
      <div class="pa-4">
        <p class="text-body-1 mb-4">
          {{ t("rom.delete-manual-confirm-title") }}
        </p>
        <p class="text-body-2 text-medium-emphasis">
          {{ t("rom.delete-manual-confirm-body") }}
        </p>
      </div>
    </template>
    <template #append>
      <v-divider />
      <v-row class="justify-center pa-2" no-gutters>
        <v-btn-group divided density="compact">
          <v-btn class="bg-toplayer" @click="showConfirmDeleteManual = false">
            {{ t("common.cancel") }}
          </v-btn>
          <v-btn class="text-romm-red bg-toplayer" @click="removeManual">
            {{ t("rom.delete-manual-button") }}
          </v-btn>
        </v-btn-group>
      </v-row>
    </template>
  </RDialog>
</template>
