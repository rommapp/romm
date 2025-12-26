<script setup lang="ts">
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { computed, inject, ref } from "vue";
import { useI18n } from "vue-i18n";
import CreateExclusionDialog from "@/components/Settings/LibraryManagement/Config/Dialog/CreateExclusion.vue";
import RSection from "@/components/common/RSection.vue";
import configApi from "@/services/api/config";
import storeAuth from "@/stores/auth";
import storeConfig from "@/stores/config";
import type { Events } from "@/types/emitter";

const { t } = useI18n();
const configStore = storeConfig();
const { config } = storeToRefs(configStore);
const authStore = storeAuth();
const emitter = inject<Emitter<Events>>("emitter");
const expandedPanels = ref<number[]>([]);

const exclusions = computed(() => [
  {
    set: config.value.EXCLUDED_PLATFORMS,
    title: t("common.platform"),
    icon: "mdi-gamepad-variant-outline",
    type: "EXCLUDED_PLATFORMS",
    description: "Platforms to exclude from scanning",
  },
  {
    set: config.value.EXCLUDED_SINGLE_FILES,
    title: t("settings.excluded-single-rom-files"),
    icon: "mdi-file-remove-outline",
    type: "EXCLUDED_SINGLE_FILES",
    description: "File names to exclude from single ROM scanning",
  },
  {
    set: config.value.EXCLUDED_SINGLE_EXT,
    title: t("settings.excluded-single-rom-extensions"),
    icon: "mdi-file-code-outline",
    type: "EXCLUDED_SINGLE_EXT",
    description: "File extensions to exclude from single ROM scanning",
  },
  {
    set: config.value.EXCLUDED_MULTI_FILES,
    title: t("settings.excluded-multi-rom-files"),
    icon: "mdi-file-multiple-outline",
    type: "EXCLUDED_MULTI_FILES",
    description: "File names to exclude from multi-file ROM scanning",
  },
  {
    set: config.value.EXCLUDED_MULTI_PARTS_FILES,
    title: t("settings.excluded-multi-rom-parts-files"),
    icon: "mdi-folder-multiple-outline",
    type: "EXCLUDED_MULTI_PARTS_FILES",
    description: "File names to exclude from multi-part ROM scanning",
  },
  {
    set: config.value.EXCLUDED_MULTI_PARTS_EXT,
    title: t("settings.excluded-multi-rom-parts-extensions"),
    icon: "mdi-file-cog-outline",
    type: "EXCLUDED_MULTI_PARTS_EXT",
    description: "File extensions to exclude from multi-part ROM scanning",
  },
]);

function removeExclusion(exclusionValue: string, exclusionType: string) {
  if (configStore.isExclusionType(exclusionType)) {
    configApi.deleteExclusion({
      exclusionValue: exclusionValue,
      exclusionType: exclusionType,
    });
    configStore.removeExclusion(exclusionValue, exclusionType);
  } else {
    console.error(`Invalid exclusion type '${exclusionType}'`);
  }
}

function addExclusion(type: string, icon: string, title: string) {
  emitter?.emit("showCreateExclusionDialog", {
    type: type,
    icon: icon,
    title: title,
  });
}
</script>
<template>
  <RSection icon="mdi-cancel" :title="t('settings.excluded')">
    <template #toolbar-title-append>
      <v-tooltip bottom max-width="400">
        <template #activator="{ props }">
          <v-btn
            v-bind="props"
            size="small"
            variant="text"
            icon="mdi-information-outline"
          />
        </template>
        <div>
          <p>
            Configure which files, extensions, and platforms should be excluded
            during library scanning. Items added here will be ignored when RomM
            scans your library.
          </p>
        </div>
      </v-tooltip>
    </template>
    <template #content>
      <v-expansion-panels
        v-model="expandedPanels"
        multiple
        rounded="0"
        variant="accordion"
      >
        <v-expansion-panel
          v-for="(exclusion, index) in exclusions"
          :key="exclusion.type"
          :value="index"
          elevation="0"
          class="bg-toplayer"
        >
          <v-expansion-panel-title class="px-4">
            <template #default="{ expanded }">
              <v-row no-gutters align="center">
                <v-col cols="auto">
                  <v-icon :icon="exclusion.icon" class="mr-4" size="large" />
                </v-col>
                <v-col>
                  <div class="text-body-1 font-weight-medium">
                    {{ exclusion.title }}
                  </div>
                  <div class="text-caption text-romm-gray">
                    {{ exclusion.description }}
                  </div>
                </v-col>
                <v-col cols="auto" class="mr-4">
                  <v-btn
                    v-if="
                      authStore.scopes.includes('platforms.write') &&
                      config.CONFIG_FILE_WRITABLE &&
                      expanded
                    "
                    prepend-icon="mdi-plus"
                    variant="outlined"
                    class="text-primary mr-2"
                    size="small"
                    @click.stop="
                      addExclusion(
                        exclusion.type,
                        exclusion.icon,
                        exclusion.title,
                      )
                    "
                  >
                    {{ t("common.add") }}
                  </v-btn>
                  <v-chip size="small" label>
                    {{ exclusion.set.length }}
                    {{ exclusion.set.length === 1 ? "item" : "items" }}
                  </v-chip>
                </v-col>
              </v-row>
            </template>
          </v-expansion-panel-title>
          <v-expansion-panel-text class="pa-1 bg-surface">
            <div v-if="exclusion.set.length === 0" class="text-center py-8">
              <v-icon
                :icon="exclusion.icon"
                size="48"
                class="mb-2 opacity-50"
              />
              <div class="text-body-2 text-romm-gray">
                No exclusions configured
              </div>
            </div>
            <div v-else class="d-flex flex-wrap">
              <v-chip
                v-for="exclusionValue in exclusion.set"
                :key="exclusionValue"
                variant="tonal"
                label
                size="default"
                class="ma-1"
              >
                <span class="font-weight-medium">{{ exclusionValue }}</span>
                <template
                  v-if="
                    authStore.scopes.includes('platforms.write') &&
                    config.CONFIG_FILE_WRITABLE
                  "
                  #append
                >
                  <v-icon
                    icon="mdi-close-circle"
                    size="18"
                    class="ml-2 cursor-pointer"
                    @click="removeExclusion(exclusionValue, exclusion.type)"
                  />
                </template>
              </v-chip>
            </div>
          </v-expansion-panel-text>
        </v-expansion-panel>
      </v-expansion-panels>
      <CreateExclusionDialog />
    </template>
  </RSection>
</template>

<style scoped>
.gap-2 {
  gap: 0.5rem;
}

.cursor-pointer {
  cursor: pointer;
}

.opacity-50 {
  opacity: 0.5;
}
</style>
