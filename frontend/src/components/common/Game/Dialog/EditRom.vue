<script setup lang="ts">
import type { Emitter } from "mitt";
import { computed, inject, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute } from "vue-router";
import { useDisplay } from "vuetify";
import GameCard from "@/components/common/Game/Card/Base.vue";
import RDialog from "@/components/common/RDialog.vue";
import romApi, { type UpdateRom } from "@/services/api/rom";
import storeGalleryView from "@/stores/galleryView";
import storeHeartbeat from "@/stores/heartbeat";
import storePlatforms from "@/stores/platforms";
import storeRoms, { type SimpleRom } from "@/stores/roms";
import storeUpload from "@/stores/upload";
import type { Events } from "@/types/emitter";
import { getMissingCoverImage } from "@/utils/covers";

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
const platfotmsStore = storePlatforms();
const galleryViewStore = storeGalleryView();
const uploadStore = storeUpload();
const validForm = ref(false);
const showConfirmDeleteManual = ref(false);
const emitter = inject<Emitter<Events>>("emitter");

// Metadata JSON editing
const igdbMetadataJson = ref("");
const mobyMetadataJson = ref("");
const ssMetadataJson = ref("");
const launchboxMetadataJson = ref("");
const hasheousMetadataJson = ref("");
const flashpointMetadataJson = ref("");
const hltbMetadataJson = ref("");

// Edit states for each metadata type
const isEditingIgdb = ref(false);
const isEditingMoby = ref(false);
const isEditingSs = ref(false);
const isEditingLaunchbox = ref(false);
const isEditingHasheous = ref(false);
const isEditingFlashpoint = ref(false);
const isEditingHltb = ref(false);
emitter?.on("showEditRomDialog", (romToEdit: SimpleRom) => {
  show.value = true;
  rom.value = romToEdit;
  removeCover.value = false;
  initializeMetadataJson();
});
emitter?.on("updateUrlCover", (url_cover) => {
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
      msg: "Manual removed successfully",
      icon: "mdi-check-bold",
      color: "green",
    });
  } catch (error: any) {
    emitter?.emit("snackbarShow", {
      msg: `Failed to remove manual: ${error.response?.data?.detail || error.message}`,
      icon: "mdi-close-circle",
      color: "red",
    });
  }
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
  rom.value = null;
  imagePreviewUrl.value = "";
  showConfirmDeleteManual.value = false;
}

function initializeMetadataJson() {
  if (!rom.value) return;

  igdbMetadataJson.value = rom.value.igdb_metadata
    ? JSON.stringify(rom.value.igdb_metadata, null, 2)
    : "";
  mobyMetadataJson.value = rom.value.moby_metadata
    ? JSON.stringify(rom.value.moby_metadata, null, 2)
    : "";
  ssMetadataJson.value = rom.value.ss_metadata
    ? JSON.stringify(rom.value.ss_metadata, null, 2)
    : "";
  launchboxMetadataJson.value = rom.value.launchbox_metadata
    ? JSON.stringify(rom.value.launchbox_metadata, null, 2)
    : "";
  hasheousMetadataJson.value = rom.value.hasheous_metadata
    ? JSON.stringify(rom.value.hasheous_metadata, null, 2)
    : "";
  flashpointMetadataJson.value = rom.value.flashpoint_metadata
    ? JSON.stringify(rom.value.flashpoint_metadata, null, 2)
    : "";
  hltbMetadataJson.value = rom.value.hltb_metadata
    ? JSON.stringify(rom.value.hltb_metadata, null, 2)
    : "";

  // Reset edit states
  isEditingIgdb.value = false;
  isEditingMoby.value = false;
  isEditingSs.value = false;
  isEditingLaunchbox.value = false;
  isEditingHasheous.value = false;
  isEditingFlashpoint.value = false;
  isEditingHltb.value = false;
}

function validateJson(value: string): boolean | string {
  if (!value || value.trim() === "") return true;

  try {
    JSON.parse(value);
    return true;
  } catch (error) {
    return "Invalid JSON format";
  }
}

function startEdit(metadataType: string) {
  switch (metadataType) {
    case "igdb":
      isEditingIgdb.value = true;
      break;
    case "moby":
      isEditingMoby.value = true;
      break;
    case "ss":
      isEditingSs.value = true;
      break;
    case "launchbox":
      isEditingLaunchbox.value = true;
      break;
    case "hasheous":
      isEditingHasheous.value = true;
      break;
    case "flashpoint":
      isEditingFlashpoint.value = true;
      break;
    case "hltb":
      isEditingHltb.value = true;
      break;
  }
}

function cancelEdit(metadataType: string) {
  // Reset to original value
  if (!rom.value) return;

  switch (metadataType) {
    case "igdb":
      isEditingIgdb.value = false;
      igdbMetadataJson.value = rom.value.igdb_metadata
        ? JSON.stringify(rom.value.igdb_metadata, null, 2)
        : "";
      break;
    case "moby":
      isEditingMoby.value = false;
      mobyMetadataJson.value = rom.value.moby_metadata
        ? JSON.stringify(rom.value.moby_metadata, null, 2)
        : "";
      break;
    case "ss":
      isEditingSs.value = false;
      ssMetadataJson.value = rom.value.ss_metadata
        ? JSON.stringify(rom.value.ss_metadata, null, 2)
        : "";
      break;
    case "launchbox":
      isEditingLaunchbox.value = false;
      launchboxMetadataJson.value = rom.value.launchbox_metadata
        ? JSON.stringify(rom.value.launchbox_metadata, null, 2)
        : "";
      break;
    case "hasheous":
      isEditingHasheous.value = false;
      hasheousMetadataJson.value = rom.value.hasheous_metadata
        ? JSON.stringify(rom.value.hasheous_metadata, null, 2)
        : "";
      break;
    case "flashpoint":
      isEditingFlashpoint.value = false;
      flashpointMetadataJson.value = rom.value.flashpoint_metadata
        ? JSON.stringify(rom.value.flashpoint_metadata, null, 2)
        : "";
      break;
    case "hltb":
      isEditingHltb.value = false;
      hltbMetadataJson.value = rom.value.hltb_metadata
        ? JSON.stringify(rom.value.hltb_metadata, null, 2)
        : "";
      break;
  }
}

async function saveMetadata(metadataType: string) {
  if (!rom.value) return;

  let jsonValue = "";
  switch (metadataType) {
    case "igdb":
      jsonValue = igdbMetadataJson.value;
      break;
    case "moby":
      jsonValue = mobyMetadataJson.value;
      break;
    case "ss":
      jsonValue = ssMetadataJson.value;
      break;
    case "launchbox":
      jsonValue = launchboxMetadataJson.value;
      break;
    case "hasheous":
      jsonValue = hasheousMetadataJson.value;
      break;
    case "flashpoint":
      jsonValue = flashpointMetadataJson.value;
      break;
    case "hltb":
      jsonValue = hltbMetadataJson.value;
      break;
    default:
      return;
  }

  if (!jsonValue || jsonValue.trim() === "") {
    emitter?.emit("snackbarShow", {
      msg: "No metadata to save",
      icon: "mdi-information",
      color: "info",
      timeout: 3000,
    });
    return;
  }

  try {
    // Prepare raw metadata object
    const rawMetadata: any = {};
    switch (metadataType) {
      case "igdb":
        rawMetadata.igdb_metadata = jsonValue;
        break;
      case "moby":
        rawMetadata.moby_metadata = jsonValue;
        break;
      case "ss":
        rawMetadata.ss_metadata = jsonValue;
        break;
      case "launchbox":
        rawMetadata.launchbox_metadata = jsonValue;
        break;
      case "hasheous":
        rawMetadata.hasheous_metadata = jsonValue;
        break;
      case "flashpoint":
        rawMetadata.flashpoint_metadata = jsonValue;
        break;
      case "hltb":
        rawMetadata.hltb_metadata = jsonValue;
        break;
    }

    // Update the ROM with raw metadata
    await handleRomUpdate(
      {
        rom: {
          ...rom.value,
          raw_metadata: rawMetadata,
        },
      },
      `${metadataType.toUpperCase()} metadata updated successfully!`,
    );

    // Exit edit mode
    switch (metadataType) {
      case "igdb":
        isEditingIgdb.value = false;
        break;
      case "moby":
        isEditingMoby.value = false;
        break;
      case "ss":
        isEditingSs.value = false;
        break;
      case "launchbox":
        isEditingLaunchbox.value = false;
        break;
      case "hasheous":
        isEditingHasheous.value = false;
        break;
      case "flashpoint":
        isEditingFlashpoint.value = false;
        break;
      case "hltb":
        isEditingHltb.value = false;
        break;
    }
  } catch (error) {
    emitter?.emit("snackbarShow", {
      msg: "Invalid JSON format",
      icon: "mdi-close-circle",
      color: "red",
      timeout: 3000,
    });
  }
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
              @keyup.enter="updateRom"
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
              @keyup.enter="updateRom"
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
            <v-chip
              :variant="rom.has_manual ? 'flat' : 'tonal'"
              label
              size="large"
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
        <v-expansion-panels class="mt-6">
          <v-expansion-panel>
            <v-expansion-panel-title class="bg-toplayer">
              <v-icon class="mr-2">mdi-database</v-icon>
              {{ t("rom.metadata-ids") }}
            </v-expansion-panel-title>
            <v-expansion-panel-text class="mt-4 px-2">
              <v-row no-gutters class="my-2">
                <v-col cols="12" md="6" xl="4" class="pa-2">
                  <v-text-field
                    hide-details
                    clearable
                    :model-value="rom.igdb_id?.toString() || null"
                    label="IGDB ID"
                    variant="outlined"
                    @update:model-value="
                      (value) =>
                        rom && (rom.igdb_id = value ? parseInt(value) : null)
                    "
                  />
                </v-col>
                <v-col cols="12" md="6" xl="4" class="pa-2">
                  <v-text-field
                    hide-details
                    clearable
                    :model-value="rom.moby_id?.toString() || null"
                    label="MobyGames ID"
                    variant="outlined"
                    @update:model-value="
                      (value) =>
                        rom && (rom.moby_id = value ? parseInt(value) : null)
                    "
                  />
                </v-col>
                <v-col cols="12" md="6" xl="4" class="pa-2">
                  <v-text-field
                    hide-details
                    clearable
                    :model-value="rom.ss_id?.toString() || null"
                    label="ScreenScraper ID"
                    variant="outlined"
                    @update:model-value="
                      (value) =>
                        rom && (rom.ss_id = value ? parseInt(value) : null)
                    "
                  />
                </v-col>
                <v-col cols="12" md="6" xl="4" class="pa-2">
                  <v-text-field
                    hide-details
                    clearable
                    :model-value="rom.ra_id?.toString() || null"
                    label="RetroAchievements ID"
                    variant="outlined"
                    @update:model-value="
                      (value) =>
                        rom && (rom.ra_id = value ? parseInt(value) : null)
                    "
                  />
                </v-col>
                <v-col cols="12" md="6" xl="4" class="pa-2">
                  <v-text-field
                    hide-details
                    clearable
                    :model-value="rom.launchbox_id?.toString() || null"
                    label="LaunchBox ID"
                    variant="outlined"
                    @update:model-value="
                      (value) =>
                        rom &&
                        (rom.launchbox_id = value ? parseInt(value) : null)
                    "
                  />
                </v-col>
                <v-col cols="12" md="6" xl="4" class="pa-2">
                  <v-text-field
                    hide-details
                    clearable
                    :model-value="rom.sgdb_id?.toString() || null"
                    label="SteamGridDB ID"
                    variant="outlined"
                    @update:model-value="
                      (value) =>
                        rom && (rom.sgdb_id = value ? parseInt(value) : null)
                    "
                  />
                </v-col>
                <v-col cols="12" md="6" xl="4" class="pa-2">
                  <v-text-field
                    hide-details
                    clearable
                    :model-value="rom.hasheous_id?.toString() || null"
                    label="Hasheous ID"
                    variant="outlined"
                    @update:model-value="
                      (value) =>
                        rom &&
                        (rom.hasheous_id = value ? parseInt(value) : null)
                    "
                  />
                </v-col>
                <v-col cols="12" md="6" xl="4" class="pa-2">
                  <v-text-field
                    hide-details
                    clearable
                    :model-value="rom.flashpoint_id || null"
                    label="Flashpoint ID"
                    variant="outlined"
                    @update:model-value="
                      (value) => rom && (rom.flashpoint_id = value || null)
                    "
                  />
                </v-col>
                <v-col cols="12" md="6" xl="4" class="pa-2">
                  <v-text-field
                    hide-details
                    clearable
                    :model-value="rom.hltb_id?.toString() || null"
                    label="HowLongToBeat ID"
                    variant="outlined"
                    @update:model-value="
                      (value) =>
                        rom && (rom.hltb_id = value ? parseInt(value) : null)
                    "
                  />
                </v-col>
              </v-row>
            </v-expansion-panel-text>
          </v-expansion-panel>

          <!-- IGDB Metadata -->
          <v-expansion-panel v-if="rom.igdb_id">
            <v-expansion-panel-title class="bg-toplayer">
              <v-avatar size="26" rounded class="mr-2">
                <v-img src="/assets/scrappers/igdb.png" />
              </v-avatar>
              IGDB Raw Metadata
            </v-expansion-panel-title>
            <v-expansion-panel-text class="mt-4 px-2">
              <v-textarea
                v-model="igdbMetadataJson"
                label="IGDB Metadata JSON"
                variant="outlined"
                rows="8"
                hide-details
                :readonly="!isEditingIgdb"
                :rules="[validateJson]"
              />
              <v-btn-group
                divided
                density="compact"
                rounded="0"
                class="my-2 d-flex justify-center"
              >
                <v-btn
                  v-if="!isEditingIgdb"
                  color="primary"
                  variant="flat"
                  @click="startEdit('igdb')"
                >
                  Edit
                </v-btn>
                <template v-else>
                  <v-btn
                    color="success"
                    variant="flat"
                    @click="saveMetadata('igdb')"
                  >
                    Save
                  </v-btn>
                  <v-btn
                    color="error"
                    variant="flat"
                    @click="cancelEdit('igdb')"
                  >
                    Cancel
                  </v-btn>
                </template>
              </v-btn-group>
            </v-expansion-panel-text>
          </v-expansion-panel>

          <!-- MobyGames Metadata -->
          <v-expansion-panel v-if="rom.moby_id">
            <v-expansion-panel-title class="bg-toplayer">
              <v-avatar size="26" rounded class="mr-2">
                <v-img src="/assets/scrappers/moby.png" />
              </v-avatar>
              MobyGames Raw Metadata
            </v-expansion-panel-title>
            <v-expansion-panel-text class="mt-4 px-2">
              <v-textarea
                v-model="mobyMetadataJson"
                label="MobyGames Metadata JSON"
                variant="outlined"
                rows="8"
                hide-details
                :readonly="!isEditingMoby"
                :rules="[validateJson]"
              />
              <v-btn-group
                divided
                density="compact"
                rounded="0"
                class="my-2 d-flex justify-center"
              >
                <v-btn
                  v-if="!isEditingMoby"
                  color="primary"
                  variant="flat"
                  @click="startEdit('moby')"
                >
                  Edit
                </v-btn>
                <template v-else>
                  <v-btn
                    color="success"
                    variant="flat"
                    @click="saveMetadata('moby')"
                  >
                    Save
                  </v-btn>
                  <v-btn
                    color="error"
                    variant="flat"
                    @click="cancelEdit('moby')"
                  >
                    Cancel
                  </v-btn>
                </template>
              </v-btn-group>
            </v-expansion-panel-text>
          </v-expansion-panel>

          <!-- ScreenScraper Metadata -->
          <v-expansion-panel v-if="rom.ss_id">
            <v-expansion-panel-title class="bg-toplayer">
              <v-avatar size="26" rounded class="mr-2">
                <v-img src="/assets/scrappers/ss.png" />
              </v-avatar>
              ScreenScraper Raw Metadata
            </v-expansion-panel-title>
            <v-expansion-panel-text class="mt-4 px-2">
              <v-textarea
                v-model="ssMetadataJson"
                label="ScreenScraper Metadata JSON"
                variant="outlined"
                rows="8"
                hide-details
                :readonly="!isEditingSs"
                :rules="[validateJson]"
              />
              <v-btn-group
                divided
                density="compact"
                rounded="0"
                class="my-2 d-flex justify-center"
              >
                <v-btn
                  v-if="!isEditingSs"
                  color="primary"
                  variant="flat"
                  @click="startEdit('ss')"
                >
                  Edit
                </v-btn>
                <template v-else>
                  <v-btn
                    color="success"
                    variant="flat"
                    @click="saveMetadata('ss')"
                  >
                    Save
                  </v-btn>
                  <v-btn color="error" variant="flat" @click="cancelEdit('ss')">
                    Cancel
                  </v-btn>
                </template>
              </v-btn-group>
            </v-expansion-panel-text>
          </v-expansion-panel>

          <!-- LaunchBox Metadata -->
          <v-expansion-panel v-if="rom.launchbox_id">
            <v-expansion-panel-title class="bg-toplayer">
              <v-avatar size="26" rounded class="mr-2">
                <v-img src="/assets/scrappers/launchbox.png" />
              </v-avatar>
              LaunchBox Raw Metadata
            </v-expansion-panel-title>
            <v-expansion-panel-text class="mt-4 px-2">
              <v-textarea
                v-model="launchboxMetadataJson"
                label="LaunchBox Metadata JSON"
                variant="outlined"
                rows="8"
                hide-details
                :readonly="!isEditingLaunchbox"
                :rules="[validateJson]"
              />
              <v-btn-group
                divided
                density="compact"
                rounded="0"
                class="my-2 d-flex justify-center"
              >
                <v-btn
                  v-if="!isEditingLaunchbox"
                  color="primary"
                  variant="flat"
                  @click="startEdit('launchbox')"
                >
                  Edit
                </v-btn>
                <template v-else>
                  <v-btn
                    color="success"
                    variant="flat"
                    @click="saveMetadata('launchbox')"
                  >
                    Save
                  </v-btn>
                  <v-btn
                    color="error"
                    variant="flat"
                    @click="cancelEdit('launchbox')"
                  >
                    Cancel
                  </v-btn>
                </template>
              </v-btn-group>
            </v-expansion-panel-text>
          </v-expansion-panel>

          <!-- Hasheous Metadata -->
          <v-expansion-panel v-if="rom.hasheous_id">
            <v-expansion-panel-title class="bg-toplayer">
              <v-avatar size="26" rounded class="mr-2">
                <v-img src="/assets/scrappers/hasheous.png" />
              </v-avatar>
              Hasheous Raw Metadata
            </v-expansion-panel-title>
            <v-expansion-panel-text class="mt-4 px-2">
              <v-textarea
                v-model="hasheousMetadataJson"
                label="Hasheous Metadata JSON"
                variant="outlined"
                rows="8"
                hide-details
                :readonly="!isEditingHasheous"
                :rules="[validateJson]"
              />
              <v-btn-group
                divided
                density="compact"
                rounded="0"
                class="my-2 d-flex justify-center"
              >
                <v-btn
                  v-if="!isEditingHasheous"
                  color="primary"
                  variant="flat"
                  @click="startEdit('hasheous')"
                >
                  Edit
                </v-btn>
                <template v-else>
                  <v-btn
                    color="success"
                    variant="flat"
                    @click="saveMetadata('hasheous')"
                  >
                    Save
                  </v-btn>
                  <v-btn
                    color="error"
                    variant="flat"
                    @click="cancelEdit('hasheous')"
                  >
                    Cancel
                  </v-btn>
                </template>
              </v-btn-group>
            </v-expansion-panel-text>
          </v-expansion-panel>

          <!-- Flashpoint Metadata -->
          <v-expansion-panel v-if="rom.flashpoint_id">
            <v-expansion-panel-title class="bg-toplayer">
              <v-avatar size="26" rounded class="mr-2">
                <v-img src="/assets/scrappers/flashpoint.png" />
              </v-avatar>
              Flashpoint Raw Metadata
            </v-expansion-panel-title>
            <v-expansion-panel-text class="mt-4 px-2">
              <v-textarea
                v-model="flashpointMetadataJson"
                label="Flashpoint Metadata JSON"
                variant="outlined"
                rows="8"
                hide-details
                :readonly="!isEditingFlashpoint"
                :rules="[validateJson]"
              />
              <v-btn-group
                divided
                density="compact"
                rounded="0"
                class="my-2 d-flex justify-center"
              >
                <v-btn
                  v-if="!isEditingFlashpoint"
                  color="primary"
                  variant="flat"
                  @click="startEdit('flashpoint')"
                >
                  Edit
                </v-btn>
                <template v-else>
                  <v-btn
                    color="success"
                    variant="flat"
                    @click="saveMetadata('flashpoint')"
                  >
                    Save
                  </v-btn>
                  <v-btn
                    color="error"
                    variant="flat"
                    @click="cancelEdit('flashpoint')"
                  >
                    Cancel
                  </v-btn>
                </template>
              </v-btn-group>
            </v-expansion-panel-text>
          </v-expansion-panel>

          <!-- HLTB Metadata -->
          <v-expansion-panel v-if="rom.hltb_id">
            <v-expansion-panel-title class="bg-toplayer">
              <v-avatar size="26" rounded class="mr-2">
                <v-img src="/assets/scrappers/hltb.png" />
              </v-avatar>
              HLTB Raw Metadata
            </v-expansion-panel-title>
            <v-expansion-panel-text class="mt-4 px-2">
              <v-textarea
                v-model="hltbMetadataJson"
                label="HLTB Metadata JSON"
                variant="outlined"
                rows="8"
                hide-details
                :readonly="!isEditingHltb"
                :rules="[validateJson]"
              />
              <v-btn-group
                divided
                density="compact"
                rounded="0"
                class="my-2 d-flex justify-center"
              >
                <v-btn
                  v-if="!isEditingHltb"
                  color="primary"
                  variant="flat"
                  @click="startEdit('hltb')"
                >
                  Edit
                </v-btn>
                <template v-else>
                  <v-btn
                    color="success"
                    variant="flat"
                    @click="saveMetadata('hltb')"
                  >
                    Save
                  </v-btn>
                  <v-btn
                    color="error"
                    variant="flat"
                    @click="cancelEdit('hltb')"
                  >
                    Cancel
                  </v-btn>
                </template>
              </v-btn-group>
            </v-expansion-panel-text>
          </v-expansion-panel>
        </v-expansion-panels>
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
  </RDialog>

  <RDialog
    v-model="showConfirmDeleteManual"
    icon="mdi-alert-circle"
    :width="lgAndUp ? '400px' : '90vw'"
  >
    <template #content>
      <div class="pa-4">
        <p class="text-body-1 mb-4">
          Are you sure you want to delete the manual?
        </p>
        <p class="text-body-2 text-medium-emphasis">
          The manual file will be permanently removed from the filesystem.
        </p>
      </div>
    </template>
    <template #append>
      <v-divider />
      <v-row class="justify-center pa-2" no-gutters>
        <v-btn-group divided density="compact">
          <v-btn class="bg-toplayer" @click="showConfirmDeleteManual = false">
            Cancel
          </v-btn>
          <v-btn class="text-romm-red bg-toplayer" @click="removeManual">
            Delete
          </v-btn>
        </v-btn-group>
      </v-row>
    </template>
  </RDialog>
</template>
