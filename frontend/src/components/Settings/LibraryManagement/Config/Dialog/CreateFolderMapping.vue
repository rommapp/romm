<script setup lang="ts">
import type { Emitter } from "mitt";
import { computed, inject, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useDisplay } from "vuetify";
import PlatformIcon from "@/components/common/Platform/PlatformIcon.vue";
import RDialog from "@/components/common/RDialog.vue";
import configApi from "@/services/api/config";
import platformApi from "@/services/api/platform";
import storeConfig from "@/stores/config";
import storeHeartbeat from "@/stores/heartbeat";
import { type Platform } from "@/stores/platforms";
import type { Events } from "@/types/emitter";

const { t } = useI18n();
const { mdAndUp } = useDisplay();
const show = ref(false);
const configStore = storeConfig();
const emitter = inject<Emitter<Events>>("emitter");
const supportedPlatforms = ref<Platform[]>();
const heartbeat = storeHeartbeat();

const fsSlugToCreate = ref<string>("");
const selectedPlatform = ref<Platform>();
const mappingType = ref<"alias" | "variant">("alias");
const isEditing = ref(false);
const originalFsSlug = ref<string>("");
const originalMappingType = ref<"alias" | "variant">("alias");

// Filter folders based on mapping type
const availableFolders = computed(() => {
  return heartbeat.value.FILESYSTEM.FS_PLATFORMS.filter((folder) => {
    // When editing, include the current folder
    if (isEditing.value && folder === originalFsSlug.value) {
      return true;
    }

    if (mappingType.value === "alias") {
      // For alias, exclude folders already in PLATFORMS_VERSIONS
      return !Object.keys(configStore.config.PLATFORMS_VERSIONS).includes(
        folder,
      );
    } else {
      // For variant, exclude folders already in PLATFORMS_BINDING
      return !Object.keys(configStore.config.PLATFORMS_BINDING).includes(
        folder,
      );
    }
  });
});

emitter?.on(
  "showCreateFolderMappingDialog",
  async (
    payload: { fsSlug: string; slug: string; type: "alias" | "variant" } | null,
  ) => {
    await platformApi
      .getSupportedPlatforms()
      .then(({ data }) => {
        supportedPlatforms.value = data.sort((a, b) => {
          return a.name.localeCompare(b.name);
        });
      })
      .catch(({ response, message }) => {
        emitter?.emit("snackbarShow", {
          msg: `Unable to get supported platforms: ${
            response?.data?.detail || response?.statusText || message
          }`,
          icon: "mdi-close-circle",
          color: "red",
          timeout: 4000,
        });
      });

    if (payload) {
      // Edit mode
      isEditing.value = true;
      originalFsSlug.value = payload.fsSlug;
      originalMappingType.value = payload.type;
      fsSlugToCreate.value = payload.fsSlug;
      mappingType.value = payload.type;
      selectedPlatform.value = supportedPlatforms.value?.find(
        (p) => p.slug === payload.slug,
      );
    } else {
      // Create mode
      isEditing.value = false;
      originalFsSlug.value = "";
      originalMappingType.value = "alias";
      fsSlugToCreate.value = "";
      selectedPlatform.value = undefined;
      mappingType.value = "alias";
    }

    show.value = true;
  },
);

function createMapping() {
  if (!selectedPlatform.value || !fsSlugToCreate.value) return;

  if (isEditing.value) {
    // Edit mode: delete old and create new
    const deletePromise =
      originalMappingType.value === "alias"
        ? configApi.deletePlatformBindConfig({ fsSlug: originalFsSlug.value })
        : configApi.deletePlatformVersionConfig({
            fsSlug: originalFsSlug.value,
          });

    deletePromise
      .then(() => {
        // Remove from store
        if (originalMappingType.value === "alias") {
          configStore.removePlatformBinding(originalFsSlug.value);
        } else {
          configStore.removePlatformVersion(originalFsSlug.value);
        }

        // Now add the new one
        return mappingType.value === "alias"
          ? configApi.addPlatformBindConfig({
              fsSlug: fsSlugToCreate.value,
              slug: selectedPlatform.value!.slug,
            })
          : configApi.addPlatformVersionConfig({
              fsSlug: fsSlugToCreate.value,
              slug: selectedPlatform.value!.slug,
            });
      })
      .then(() => {
        if (selectedPlatform.value) {
          if (mappingType.value === "alias") {
            configStore.addPlatformBinding(
              fsSlugToCreate.value,
              selectedPlatform.value.slug,
            );
          } else {
            configStore.addPlatformVersion(
              fsSlugToCreate.value,
              selectedPlatform.value.slug,
            );
          }
        }
        closeDialog();
      })
      .catch(({ response, message }) => {
        emitter?.emit("snackbarShow", {
          msg: `${response?.data?.detail || response?.statusText || message}`,
          icon: "mdi-close-circle",
          color: "red",
          timeout: 4000,
        });
      });
  } else {
    // Create mode
    if (mappingType.value === "alias") {
      configApi
        .addPlatformBindConfig({
          fsSlug: fsSlugToCreate.value,
          slug: selectedPlatform.value.slug,
        })
        .then(() => {
          if (selectedPlatform.value) {
            configStore.addPlatformBinding(
              fsSlugToCreate.value,
              selectedPlatform.value.slug,
            );
          }
          closeDialog();
        })
        .catch(({ response, message }) => {
          emitter?.emit("snackbarShow", {
            msg: `${response?.data?.detail || response?.statusText || message}`,
            icon: "mdi-close-circle",
            color: "red",
            timeout: 4000,
          });
        });
    } else {
      configApi
        .addPlatformVersionConfig({
          fsSlug: fsSlugToCreate.value,
          slug: selectedPlatform.value.slug,
        })
        .then(() => {
          if (selectedPlatform.value) {
            configStore.addPlatformVersion(
              fsSlugToCreate.value,
              selectedPlatform.value.slug,
            );
          }
          closeDialog();
        })
        .catch(({ response, message }) => {
          emitter?.emit("snackbarShow", {
            msg: `${response?.data?.detail || response?.statusText || message}`,
            icon: "mdi-close-circle",
            color: "red",
            timeout: 4000,
          });
        });
    }
  }
}

function closeDialog() {
  show.value = false;
  originalFsSlug.value = "";
  fsSlugToCreate.value = "";
  selectedPlatform.value = undefined;
}

function getMappingTypeDescription(type: "alias" | "variant"): string {
  if (type === "alias") {
    return t("settings.folder-alias-description");
  } else {
    return t("settings.platform-variant-description");
  }
}
</script>

<template>
  <RDialog
    v-model="show"
    :width="mdAndUp ? '50vw' : '95vw'"
    @close="closeDialog"
  >
    <template #header>
      <v-row class="align-center" no-gutters>
        <v-col cols="10">
          <v-icon icon="mdi-folder-cog" class="ml-5" />
          <v-icon icon="mdi-menu-right" class="ml-1 text-romm-gray" />
          <v-icon
            :icon="isEditing ? 'mdi-pencil' : 'mdi-plus-circle'"
            class="ml-1 text-primary"
          />
        </v-col>
      </v-row>
    </template>
    <template #content>
      <v-row class="px-4 pt-4 align-center" no-gutters>
        <v-col cols="12">
          <v-card-text class="pa-0">
            <p class="text-sm text-romm-gray mb-3">
              {{ t("settings.add-mapping-type") }}
            </p>
            <v-radio-group v-model="mappingType" class="mt-2">
              <v-radio value="alias" class="mb-2">
                <template #label>
                  <div class="ml-2">
                    <div class="font-weight-medium">
                      {{ t("settings.folder-alias") }}
                    </div>
                    <div class="text-xs text-romm-gray">
                      {{ getMappingTypeDescription("alias") }}
                    </div>
                  </div>
                </template>
              </v-radio>
              <v-radio value="variant">
                <template #label>
                  <div class="ml-2">
                    <div class="font-weight-medium">
                      {{ t("settings.platform-variant") }}
                    </div>
                    <div class="text-xs text-romm-gray">
                      {{ getMappingTypeDescription("variant") }}
                    </div>
                  </div>
                </template>
              </v-radio>
            </v-radio-group>
          </v-card-text>
        </v-col>
      </v-row>
      <v-row class="px-6 pb-6 mt-2 align-center" no-gutters>
        <v-col cols="6">
          <v-select
            v-model="fsSlugToCreate"
            :items="availableFolders"
            :label="
              mappingType === 'alias'
                ? t('settings.folder-name')
                : t('settings.variant-folder')
            "
            variant="outlined"
            required
            hide-details
          >
            <template #append>
              <v-icon icon="mdi-menu-right" class="mr-4 text-romm-gray" />
            </template>
          </v-select>
        </v-col>
        <v-col cols="6">
          <v-autocomplete
            v-model="selectedPlatform"
            class="text-primary ml-2"
            :label="
              mappingType === 'alias'
                ? t('settings.romm-platform')
                : t('settings.parent-platform')
            "
            :items="supportedPlatforms"
            color="primary"
            base-color="primary"
            variant="outlined"
            required
            return-object
            item-title="name"
            hide-details
          >
            <template #item="{ props, item }">
              <v-list-item
                class="py-2"
                v-bind="props"
                :title="item.raw.name ?? ''"
              >
                <template #prepend>
                  <PlatformIcon
                    :key="item.raw.slug"
                    :size="35"
                    :slug="item.raw.slug"
                    :name="item.raw.name"
                    :fs-slug="item.raw.fs_slug"
                  />
                </template>
              </v-list-item>
            </template>
            <template #selection="{ item }">
              <v-list-item class="px-0" :title="item.raw.name ?? ''">
                <template #prepend>
                  <PlatformIcon
                    :key="item.raw.slug"
                    :size="35"
                    :slug="item.raw.slug"
                    :name="item.raw.name"
                    :fs-slug="item.raw.fs_slug"
                  />
                </template>
              </v-list-item>
            </template>
          </v-autocomplete>
        </v-col>
      </v-row>
    </template>
    <template #footer>
      <v-row class="justify-center my-2" no-gutters>
        <v-btn-group divided density="compact">
          <v-btn class="bg-toplayer" @click="closeDialog">
            {{ t("common.cancel") }}
          </v-btn>
          <v-btn
            class="bg-toplayer text-romm-green"
            :disabled="fsSlugToCreate == '' || selectedPlatform?.slug == ''"
            :variant="
              fsSlugToCreate == '' || selectedPlatform?.slug == ''
                ? 'plain'
                : 'flat'
            "
            @click="createMapping"
          >
            {{ t("common.confirm") }}
          </v-btn>
        </v-btn-group>
      </v-row>
    </template>
  </RDialog>
</template>
