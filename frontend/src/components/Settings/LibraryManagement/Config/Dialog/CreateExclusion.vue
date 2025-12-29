<script setup lang="ts">
import type { Emitter } from "mitt";
import { inject, ref, computed } from "vue";
import { useI18n } from "vue-i18n";
import { useDisplay } from "vuetify";
import RDialog from "@/components/common/RDialog.vue";
import configApi from "@/services/api/config";
import storeConfig from "@/stores/config";
import type { Events } from "@/types/emitter";

const { t } = useI18n();
const { mdAndUp } = useDisplay();
const show = ref(false);
const emitter = inject<Emitter<Events>>("emitter");
const configStore = storeConfig();
const exclusionValue = ref();
const exclusionType = ref();
const exclusionIcon = ref();
const exclusionTitle = ref();
const preSelected = ref(false);

const exclusionTypes = computed(() => [
  {
    type: "EXCLUDED_PLATFORMS",
    title: t("common.platform"),
    icon: "mdi-gamepad-variant-outline",
    description: t("settings.exclusions-platforms-desc"),
  },
  {
    type: "EXCLUDED_SINGLE_FILES",
    title: t("settings.excluded-single-rom-files"),
    icon: "mdi-file-remove-outline",
    description: t("settings.exclusions-single-files-desc"),
  },
  {
    type: "EXCLUDED_SINGLE_EXT",
    title: t("settings.excluded-single-rom-extensions"),
    icon: "mdi-file-code-outline",
    description: t("settings.exclusions-single-ext-desc"),
  },
  {
    type: "EXCLUDED_MULTI_FILES",
    title: t("settings.excluded-multi-rom-files"),
    icon: "mdi-file-multiple-outline",
    description: t("settings.exclusions-multi-files-desc"),
  },
  {
    type: "EXCLUDED_MULTI_PARTS_FILES",
    title: t("settings.excluded-multi-rom-parts-files"),
    icon: "mdi-folder-multiple-outline",
    description: t("settings.exclusions-multi-parts-files-desc"),
  },
  {
    type: "EXCLUDED_MULTI_PARTS_EXT",
    title: t("settings.excluded-multi-rom-parts-extensions"),
    icon: "mdi-file-cog-outline",
    description: t("settings.exclusions-multi-parts-ext-desc"),
  },
]);

emitter?.on("showCreateExclusionDialog", (payload) => {
  if (payload) {
    exclusionType.value = payload.type;
    exclusionIcon.value = payload.icon;
    exclusionTitle.value = payload.title;
    preSelected.value = true;
  } else {
    exclusionType.value = null;
    exclusionIcon.value = null;
    exclusionTitle.value = null;
    preSelected.value = false;
  }
  exclusionValue.value = "";
  show.value = true;
});

function selectExclusionType(type: string, icon: string, title: string) {
  exclusionType.value = type;
  exclusionIcon.value = icon;
  exclusionTitle.value = title;
  preSelected.value = true;
}

function addExclusion() {
  if (configStore.isExclusionType(exclusionType.value)) {
    configApi.addExclusion({
      exclusionValue: exclusionValue.value,
      exclusionType: exclusionType.value,
    });
    configStore.addExclusion(exclusionType.value, exclusionValue.value);
    closeDialog();
  } else {
    console.error(`Invalid exclusion type '${exclusionType.value}'`);
  }
}

function closeDialog() {
  show.value = false;
  exclusionValue.value = "";
  exclusionType.value = null;
  exclusionIcon.value = null;
  exclusionTitle.value = null;
  preSelected.value = false;
}
</script>
<template>
  <RDialog
    v-model="show"
    icon="mdi-cancel"
    :width="mdAndUp ? '45vw' : '95vw'"
    scroll-content
    @close="closeDialog"
  >
    <template #content>
      <v-row class="align-center" no-gutters>
        <v-col cols="12">
          <v-card-text class="pa-4">
            <!-- Type Selection Step -->
            <div v-if="!preSelected">
              <p class="text-center text-sm text-romm-gray mb-6">
                {{ t("settings.select-exclusion-type") }}
              </p>
              <v-row no-gutters>
                <v-col
                  v-for="item in exclusionTypes"
                  :key="item.type"
                  class="pa-1"
                  cols="12"
                  sm="6"
                >
                  <v-card
                    variant="outlined"
                    class="cursor-pointer pa-4 text-center h-100 hover:bg-surface transition"
                    @click="
                      selectExclusionType(item.type, item.icon, item.title)
                    "
                  >
                    <v-icon
                      :icon="item.icon"
                      size="32"
                      class="text-primary mb-2"
                    />
                    <div class="text-sm font-weight-medium">
                      {{ item.title }}
                    </div>
                    <div class="text-xs text-romm-gray mt-1">
                      {{ item.description }}
                    </div>
                  </v-card>
                </v-col>
              </v-row>
            </div>
            <!-- Value Input Step -->
            <div v-else class="text-center">
              <p class="text-sm text-romm-gray mb-4">
                <v-icon :icon="exclusionIcon" class="mr-1 text-primary" />
                {{ t("settings.add-exclusion-for") }} {{ exclusionTitle }}
              </p>
              <v-text-field
                v-model="exclusionValue"
                :label="t('settings.exclusion-value')"
                :placeholder="t('settings.exclusion-placeholder')"
                variant="outlined"
                required
                hide-details
                autofocus
                @keyup.enter="addExclusion"
              >
                <template #prepend-inner>
                  <v-icon :icon="exclusionIcon" class="mr-2" />
                </template>
              </v-text-field>
            </div>
          </v-card-text>
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
            v-if="preSelected"
            class="bg-toplayer text-romm-green"
            :disabled="exclusionValue == ''"
            :variant="exclusionValue == '' ? 'plain' : 'flat'"
            @click="addExclusion"
          >
            {{ t("common.confirm") }}
          </v-btn>
        </v-btn-group>
      </v-row>
    </template>
  </RDialog>
</template>
