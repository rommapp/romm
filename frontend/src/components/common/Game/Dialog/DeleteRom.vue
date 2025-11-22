<script setup lang="ts">
import type { Emitter } from "mitt";
import { inject, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useRouter, useRoute } from "vue-router";
import { useDisplay } from "vuetify";
import RomListItem from "@/components/common/Game/ListItem.vue";
import RDialog from "@/components/common/RDialog.vue";
import { ROUTES } from "@/plugins/router";
import configApi from "@/services/api/config";
import romApi from "@/services/api/rom";
import storeConfig from "@/stores/config";
import storeRoms, { type SimpleRom } from "@/stores/roms";
import type { Events } from "@/types/emitter";

const { t } = useI18n();
const { mdAndUp } = useDisplay();
const router = useRouter();
const route = useRoute();
const show = ref(false);
const romsStore = storeRoms();
const roms = ref<SimpleRom[]>([]);
const romsToDeleteFromFs = ref<number[]>([]);
const excludeOnDelete = ref(false);
const platformId = ref<number>(0);
const emitter = inject<Emitter<Events>>("emitter");
const configStore = storeConfig();
emitter?.on("showDeleteRomDialog", (romsToDelete) => {
  roms.value = romsToDelete;
  platformId.value = roms.value[0].platform_id;
  show.value = true;
});
const HEADERS = [
  {
    title: t("common.name"),
    align: "start",
    sortable: true,
    key: "name",
  },
] as const;

async function deleteRoms() {
  await romApi
    .deleteRoms({ roms: roms.value, deleteFromFs: romsToDeleteFromFs.value })
    .then((response) => {
      emitter?.emit("snackbarShow", {
        msg:
          romsToDeleteFromFs.value.length > 0
            ? t("rom.deleted-from-filesystem", {
                count: response.data.successful_items,
              })
            : t("rom.deleted-from-database", {
                count: response.data.successful_items,
              }),
        icon: "mdi-check-bold",
        color: "green",
      });
      if (excludeOnDelete.value) {
        for (const rom of roms.value) {
          if (rom.has_simple_single_file) {
            configApi.addExclusion({
              exclusionValue: rom.fs_name,
              exclusionType: "EXCLUDED_SINGLE_FILES",
            });
            configStore.addExclusion("EXCLUDED_SINGLE_FILES", rom.fs_name);
          } else {
            configApi.addExclusion({
              exclusionValue: rom.fs_name,
              exclusionType: "EXCLUDED_MULTI_FILES",
            });
            configStore.addExclusion("EXCLUDED_MULTI_FILES", rom.fs_name);
          }
        }
      }
      romsStore.resetSelection();
      romsStore.remove(roms.value);
      romsStore.setRecentRoms(
        romsStore.recentRoms.filter(
          (r) => !roms.value.some((rom) => rom.id === r.id),
        ),
      );
      romsStore.setContinuePlayingRoms(
        romsStore.continuePlayingRoms.filter(
          (r) => !roms.value.some((rom) => rom.id === r.id),
        ),
      );
      emitter?.emit("refreshDrawer", null);
      closeDialog();
      if (route.name == "rom") {
        router.push({
          name: ROUTES.PLATFORM,
          params: { platform: platformId.value },
        });
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
}

function closeDialog() {
  romsToDeleteFromFs.value = [];
  roms.value = [];
  show.value = false;
}
</script>

<template>
  <RDialog
    v-model="show"
    icon="mdi-delete"
    scroll-content
    :width="mdAndUp ? '50vw' : '95vw'"
    @close="closeDialog"
  >
    <template #header>
      <v-row no-gutters class="justify-center">
        <span>{{ t("rom.removing-title", roms.length) }}</span>
      </v-row>
    </template>
    <template #prepend>
      <v-list-item class="text-caption text-center">
        <span>{{ t("rom.delete-select-instruction") }}</span>
      </v-list-item>
    </template>
    <template #content>
      <v-data-table-virtual
        v-model="romsToDeleteFromFs"
        :item-value="(item) => item.id"
        :items="roms"
        :width="mdAndUp ? '60vw' : '95vw'"
        :headers="HEADERS"
        show-select
      >
        <template #item.name="{ item }">
          <RomListItem :rom="item" with-filename with-size>
            <template #append-body>
              <v-row v-if="romsToDeleteFromFs.includes(item.id)" no-gutters>
                <v-col>
                  <v-chip label size="x-small" class="text-romm-red">
                    {{ t("common.removing-from-filesystem") }}
                  </v-chip>
                </v-col>
              </v-row>
            </template>
          </RomListItem>
        </template>
      </v-data-table-virtual>
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
      <v-row v-if="romsToDeleteFromFs.length > 0" no-gutters>
        <v-col>
          <v-list-item class="text-center mt-2">
            <span class="text-romm-red text-body-1">{{
              t("common.warning")
            }}</span>
            <span class="text-body-2 ml-1">{{
              t("rom.delete-filesystem-warning", romsToDeleteFromFs.length)
            }}</span>
          </v-list-item>
        </v-col>
      </v-row>
      <v-row class="justify-center my-2">
        <v-btn-group divided density="compact">
          <v-btn class="bg-toplayer" variant="flat" @click="closeDialog">
            {{ t("common.cancel") }}
          </v-btn>
          <v-btn
            class="text-romm-red bg-toplayer"
            variant="flat"
            @click="deleteRoms"
          >
            {{ t("common.confirm") }}
          </v-btn>
        </v-btn-group>
      </v-row>
    </template>
  </RDialog>
</template>
