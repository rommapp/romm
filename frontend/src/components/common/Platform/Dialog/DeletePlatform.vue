<script setup lang="ts">
import RDialog from "@/components/common/RDialog.vue";
import platformApi from "@/services/api/platform";
import storePlatforms, { type Platform } from "@/stores/platforms";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { inject, ref } from "vue";
import { useRouter } from "vue-router";
import { useDisplay } from "vuetify";
import PlatformIcon from "@/components/common/Platform/Icon.vue";
import { useI18n } from "vue-i18n";

// Props
const { t } = useI18n();
const router = useRouter();
const { lgAndUp } = useDisplay();
const platformsStore = storePlatforms();
const platform = ref<Platform | null>(null);
const show = ref(false);
const emitter = inject<Emitter<Events>>("emitter");
emitter?.on("showDeletePlatformDialog", (platformToDelete) => {
  platform.value = platformToDelete;
  show.value = true;
});

// Functions
async function deletePlatform() {
  if (!platform.value) return;

  show.value = false;
  await platformApi
    .deletePlatform({ platform: platform.value })
    .then((response) => {
      emitter?.emit("snackbarShow", {
        msg: response.data.msg,
        icon: "mdi-check-bold",
        color: "green",
      });
    })
    .catch((error) => {
      console.log(error);
      emitter?.emit("snackbarShow", {
        msg: error.response.data.detail,
        icon: "mdi-close-circle",
        color: "red",
      });
      return;
    });

  await router.push({ name: "home" });

  platformsStore.remove(platform.value);
  emitter?.emit("refreshDrawer", null);
  closeDialog();
}

function closeDialog() {
  show.value = false;
}
</script>
<template>
  <r-dialog
    v-if="platform"
    @close="closeDialog"
    v-model="show"
    icon="mdi-delete"
    scroll-content
    :width="lgAndUp ? '50vw' : '95vw'"
  >
    <template #content>
      <v-row class="justify-center align-center pa-2" no-gutters>
        <span class="mr-1">{{ t("platform.removing-platform-1") }}</span>
        <platform-icon :slug="platform.slug" :name="platform.name" />
        <span class="ml-1"
          >{{ platform.name }} - [<span class="text-romm-accent-1">{{
            platform.fs_slug
          }}</span
          >{{ t("platform.removing-platform-2") }}</span
        >
      </v-row>
    </template>
    <template #append>
      <v-row class="justify-center pa-2" no-gutters>
        <v-btn-group divided density="compact">
          <v-btn class="bg-terciary" @click="closeDialog">
            {{ t("common.cancel") }}
          </v-btn>
          <v-btn class="bg-terciary text-romm-red" @click="deletePlatform">
            {{ t("common.confirm") }}
          </v-btn>
        </v-btn-group>
      </v-row>
    </template>
  </r-dialog>
</template>
