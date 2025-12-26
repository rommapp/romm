<script setup lang="ts">
import type { Emitter } from "mitt";
import { inject, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useDisplay } from "vuetify";
import PlatformIcon from "@/components/common/Platform/PlatformIcon.vue";
import RDialog from "@/components/common/RDialog.vue";
import configApi from "@/services/api/config";
import storeConfig from "@/stores/config";
import type { Events } from "@/types/emitter";

const { t } = useI18n();
const { lgAndUp } = useDisplay();
const show = ref(false);
const emitter = inject<Emitter<Events>>("emitter");
const configStore = storeConfig();
const fsSlugToDelete = ref("");
const slugToDelete = ref("");
const typeToDelete = ref<"alias" | "variant">("alias");

emitter?.on("showDeleteFolderMappingDialog", ({ fsSlug, slug, type }) => {
  fsSlugToDelete.value = fsSlug;
  slugToDelete.value = slug;
  typeToDelete.value = type;
  show.value = true;
});

function deleteMapping() {
  const deletePromise =
    typeToDelete.value === "alias"
      ? configApi.deletePlatformBindConfig({ fsSlug: fsSlugToDelete.value })
      : configApi.deletePlatformVersionConfig({ fsSlug: fsSlugToDelete.value });

  deletePromise
    .then(() => {
      if (typeToDelete.value === "alias") {
        configStore.removePlatformBinding(fsSlugToDelete.value);
      } else {
        configStore.removePlatformVersion(fsSlugToDelete.value);
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
}
</script>
<template>
  <RDialog
    v-model="show"
    icon="mdi-delete"
    :width="lgAndUp ? '45vw' : '95vw'"
    @close="closeDialog"
  >
    <template #content>
      <v-row class="justify-center pa-2 align-center" no-gutters>
        <span class="mr-1">{{ t("settings.deleting-mapping") }}</span>
        <span class="text-primary mx-1">
          {{
            typeToDelete === "alias"
              ? t("settings.folder-alias")
              : t("settings.platform-variant")
          }}
        </span>
        <PlatformIcon
          :key="slugToDelete"
          class="mx-2"
          :slug="slugToDelete"
          :fs-slug="fsSlugToDelete"
        />
        <span>[</span>
        <span class="text-primary ml-1">{{ fsSlugToDelete }}</span>
        <span class="mx-1">:</span>
        <span class="text-primary">{{ slugToDelete }}</span>
        <span class="ml-1">].</span>
        <span class="ml-1">{{ t("settings.confirm-delete-mapping") }}</span>
      </v-row>
    </template>
    <template #footer>
      <v-row class="justify-center my-2" no-gutters>
        <v-btn-group divided density="compact">
          <v-btn class="bg-toplayer" @click="closeDialog">
            {{ t("common.cancel") }}
          </v-btn>
          <v-btn class="bg-toplayer text-romm-red" @click="deleteMapping">
            {{ t("common.confirm") }}
          </v-btn>
        </v-btn-group>
      </v-row>
    </template>
  </RDialog>
</template>
