<script setup lang="ts">
import type { Emitter } from "mitt";
import { inject, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useRouter } from "vue-router";
import { useDisplay } from "vuetify";
import PlatformIcon from "@/components/common/Platform/PlatformIcon.vue";
import RDialog from "@/components/common/RDialog.vue";
import { ROUTES } from "@/plugins/router";
import configApi from "@/services/api/config";
import platformApi from "@/services/api/platform";
import storeConfig from "@/stores/config";
import storePlatforms, { type Platform } from "@/stores/platforms";
import type { Events } from "@/types/emitter";

const { t } = useI18n();
const router = useRouter();
const { lgAndUp } = useDisplay();
const platformsStore = storePlatforms();
const configStore = storeConfig();
const platform = ref<Platform | null>(null);
const show = ref(false);
const excludeOnDelete = ref(false);
const emitter = inject<Emitter<Events>>("emitter");
emitter?.on("showDeletePlatformDialog", (platformToDelete) => {
  platform.value = platformToDelete;
  show.value = true;
});

async function deletePlatform() {
  if (!platform.value) return;

  show.value = false;
  await platformApi
    .deletePlatform({ platform: platform.value })
    .then(() => {
      emitter?.emit("snackbarShow", {
        msg: "Platform deleted",
        icon: "mdi-check-bold",
        color: "green",
      });
      if (excludeOnDelete.value && platform.value) {
        configApi.addExclusion({
          exclusionValue: platform.value.fs_slug,
          exclusionType: "EXCLUDED_PLATFORMS",
        });
        configStore.addExclusion("EXCLUDED_PLATFORMS", platform.value.fs_slug);
      }
    })
    .catch((error) => {
      console.error(error);
      emitter?.emit("snackbarShow", {
        msg: error.response.data.detail,
        icon: "mdi-close-circle",
        color: "red",
      });
      return;
    });

  await router.push({ name: ROUTES.HOME });

  platformsStore.remove(platform.value);
  emitter?.emit("refreshDrawer", null);
  closeDialog();
}

function closeDialog() {
  show.value = false;
  excludeOnDelete.value = false;
}
</script>
<template>
  <RDialog
    v-if="platform"
    v-model="show"
    icon="mdi-delete"
    scroll-content
    :width="lgAndUp ? '50vw' : '95vw'"
    @close="closeDialog"
  >
    <template #content>
      <v-row class="justify-center align-center pa-2" no-gutters>
        <span class="mr-1">{{ t("platform.removing-platform-1") }}</span>
        <PlatformIcon
          :slug="platform.slug"
          :name="platform.name"
          :fs-slug="platform.fs_slug"
        />
        <span class="ml-1"
          >{{ platform.name }} - [<span class="text-primary">{{
            platform.fs_slug
          }}</span
          >{{ t("platform.removing-platform-2") }}</span
        >
      </v-row>
    </template>
    <template #append>
      <v-row class="justify-center text-center pa-2" no-gutters>
        <v-col>
          <v-chip variant="text" @click="excludeOnDelete = !excludeOnDelete">
            <v-icon :color="excludeOnDelete ? 'accent' : ''" class="mr-1">
              {{
                excludeOnDelete
                  ? "mdi-checkbox-outline"
                  : "mdi-checkbox-blank-outline"
              }}
            </v-icon>
            {{ t("common.exclude-on-delete") }}
          </v-chip>
        </v-col>
      </v-row>
      <v-row class="justify-center pa-2" no-gutters>
        <v-btn-group divided density="compact">
          <v-btn class="bg-toplayer" @click="closeDialog">
            {{ t("common.cancel") }}
          </v-btn>
          <v-btn class="bg-toplayer text-romm-red" @click="deletePlatform">
            {{ t("common.confirm") }}
          </v-btn>
        </v-btn-group>
      </v-row>
    </template>
  </RDialog>
</template>
