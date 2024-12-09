<script setup lang="ts">
import PlatformIcon from "@/components/common/Platform/Icon.vue";
import RDialog from "@/components/common/RDialog.vue";
import configApi from "@/services/api/config";
import platformApi from "@/services/api/platform";
import storeConfig from "@/stores/config";
import { type Platform } from "@/stores/platforms";
import type { Events } from "@/types/emitter";
import storeHeartbeat from "@/stores/heartbeat";
import type { Emitter } from "mitt";
import { inject, ref } from "vue";
import { useDisplay } from "vuetify";
import { useI18n } from "vue-i18n";

// Props
const { t } = useI18n();
const { mdAndUp } = useDisplay();
const show = ref(false);
const configStore = storeConfig();
const emitter = inject<Emitter<Events>>("emitter");
const supportedPlatforms = ref<Platform[]>();
const heartbeat = storeHeartbeat();
const fsSlugToCreate = ref<string>("");
const selectedPlatform = ref<Platform>();
emitter?.on(
  "showCreatePlatformVersionDialog",
  async ({ fsSlug = "", slug = "" }) => {
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
    fsSlugToCreate.value = fsSlug;
    selectedPlatform.value = supportedPlatforms.value?.find(
      (platform) => platform.slug == slug,
    );
    show.value = true;
  },
);

// Functions
function addVersionPlatform() {
  if (!selectedPlatform.value) return;
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
    })
    .catch(({ response, message }) => {
      emitter?.emit("snackbarShow", {
        msg: `${response?.data?.detail || response?.statusText || message}`,
        icon: "mdi-close-circle",
        color: "red",
        timeout: 4000,
      });
    });
  closeDialog();
}

function closeDialog() {
  show.value = false;
  fsSlugToCreate.value = "";
}
</script>
<template>
  <r-dialog
    @close="closeDialog"
    v-model="show"
    :width="mdAndUp ? '45vw' : '95vw'"
  >
    <template #header>
      <v-row class="align-center" no-gutters>
        <v-col cols="10">
          <v-icon icon="mdi-gamepad-variant" class="ml-5" />
          <v-icon icon="mdi-menu-right" class="ml-1 text-romm-gray" />
          <v-icon icon="mdi-controller" class="ml-1 text-romm-accent-1" />
        </v-col>
      </v-row>
    </template>
    <template #content>
      <v-row class="py-2 px-4 align-center" no-gutters>
        <v-col cols="6">
          <v-select
            :items="heartbeat.value.FS_PLATFORMS"
            v-model="fsSlugToCreate"
            :label="t('settings.platform-version')"
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
            class="text-romm-accent-1"
            :label="t('settings.main-platform')"
            color="romm-accent-1"
            :items="supportedPlatforms"
            base-color="romm-accent-1"
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
                  <platform-icon
                    :key="item.raw.slug"
                    :size="35"
                    :slug="item.raw.slug"
                    :name="item.raw.name"
                  />
                </template>
              </v-list-item>
            </template>
            <template #selection="{ item }">
              <v-list-item class="px-0" :title="item.raw.name ?? ''">
                <template #prepend>
                  <platform-icon
                    :size="35"
                    :key="item.raw.slug"
                    :slug="item.raw.slug"
                    :name="item.raw.name"
                  />
                </template>
              </v-list-item>
            </template>
          </v-autocomplete>
        </v-col>
      </v-row>
    </template>
    <template #append>
      <v-row class="justify-center mb-2" no-gutters>
        <v-btn-group divided density="compact">
          <v-btn class="bg-terciary" @click="closeDialog">
            {{ t("common.cancel") }}
          </v-btn>
          <v-btn
            class="bg-terciary text-romm-green"
            :disabled="fsSlugToCreate == '' || selectedPlatform?.slug == ''"
            :variant="
              fsSlugToCreate == '' || selectedPlatform?.slug == ''
                ? 'plain'
                : 'flat'
            "
            @click="addVersionPlatform"
          >
            {{ t("common.confirm") }}
          </v-btn>
        </v-btn-group>
      </v-row>
    </template>
  </r-dialog>
</template>
