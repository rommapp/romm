<script setup lang="ts">
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { computed, inject, ref } from "vue";
import { useI18n } from "vue-i18n";
import CreateExclusionDialog from "@/components/Settings/LibraryManagement/Config/Dialog/CreateExclusion.vue";
import configApi from "@/services/api/config";
import storeAuth from "@/stores/auth";
import storeConfig from "@/stores/config";
import type { Events } from "@/types/emitter";

const { t } = useI18n();
const configStore = storeConfig();
const { config } = storeToRefs(configStore);
const authStore = storeAuth();
const emitter = inject<Emitter<Events>>("emitter");
const search = ref("");

type Row = {
  type: string;
  title: string;
  icon: string;
  value: string;
};

const HEADERS = [
  { title: t("common.name"), align: "start", key: "value" },
  { title: t("common.type"), align: "start", key: "type" },
  { title: "", align: "end", key: "actions", sortable: false },
] as const;

const rows = computed<Row[]>(() => {
  const defs = [
    {
      set: config.value.EXCLUDED_PLATFORMS || [],
      title: t("common.platform"),
      icon: "mdi-gamepad-variant-outline",
      type: "EXCLUDED_PLATFORMS",
      description: t("settings.exclusions-platforms-desc"),
    },
    {
      set: config.value.EXCLUDED_SINGLE_FILES || [],
      title: t("settings.excluded-single-rom-files"),
      icon: "mdi-file-remove-outline",
      type: "EXCLUDED_SINGLE_FILES",
      description: t("settings.exclusions-single-files-desc"),
    },
    {
      set: config.value.EXCLUDED_SINGLE_EXT || [],
      title: t("settings.excluded-single-rom-extensions"),
      icon: "mdi-file-code-outline",
      type: "EXCLUDED_SINGLE_EXT",
      description: t("settings.exclusions-single-ext-desc"),
    },
    {
      set: config.value.EXCLUDED_MULTI_FILES || [],
      title: t("settings.excluded-multi-rom-files"),
      icon: "mdi-file-multiple-outline",
      type: "EXCLUDED_MULTI_FILES",
      description: t("settings.exclusions-multi-files-desc"),
    },
    {
      set: config.value.EXCLUDED_MULTI_PARTS_FILES || [],
      title: t("settings.excluded-multi-rom-parts-files"),
      icon: "mdi-folder-multiple-outline",
      type: "EXCLUDED_MULTI_PARTS_FILES",
      description: t("settings.exclusions-multi-parts-files-desc"),
    },
    {
      set: config.value.EXCLUDED_MULTI_PARTS_EXT || [],
      title: t("settings.excluded-multi-rom-parts-extensions"),
      icon: "mdi-file-cog-outline",
      type: "EXCLUDED_MULTI_PARTS_EXT",
      description: t("settings.exclusions-multi-parts-ext-desc"),
    },
  ];

  const result: Row[] = [];
  for (const def of defs) {
    for (const v of def.set) {
      result.push({
        type: def.type,
        title: def.title,
        icon: def.icon,
        value: v,
      });
    }
  }
  return result.sort(
    (a, b) => a.title.localeCompare(b.title) || a.value.localeCompare(b.value),
  );
});

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
</script>
<template>
  <div v-if="rows.length === 0" class="text-center py-8">
    <v-icon icon="mdi-format-list-bulleted" size="48" class="mb-2 opacity-50" />
    <div class="text-body-2 text-romm-gray">
      {{ t("settings.exclusions-none") }}
    </div>
    <div
      v-if="
        authStore.scopes.includes('platforms.write') &&
        config.CONFIG_FILE_WRITABLE
      "
      class="mt-6"
    >
      <v-btn
        prepend-icon="mdi-plus"
        variant="outlined"
        class="text-primary"
        @click="emitter?.emit('showCreateExclusionDialog', null)"
      >
        {{ t("common.add") }}
      </v-btn>
    </div>
  </div>
  <template v-else>
    <v-text-field
      v-model="search"
      prepend-inner-icon="mdi-magnify"
      :label="t('common.search')"
      single-line
      hide-details
      clearable
      rounded="0"
      density="comfortable"
      class="bg-surface"
    />
    <v-data-table-virtual
      :search="search"
      :headers="HEADERS"
      :items="rows"
      :sort-by="[{ key: 'type', order: 'asc' }]"
      fixed-header
      density="comfortable"
      class="rounded bg-background"
      hide-default-footer
    >
      <template #header.actions>
        <div class="d-flex align-center flex-nowrap justify-end">
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
                {{ t("settings.exclusions-tooltip") }}
              </p>
            </div>
          </v-tooltip>
          <v-btn
            v-if="
              authStore.scopes.includes('platforms.write') &&
              config.CONFIG_FILE_WRITABLE
            "
            prepend-icon="mdi-plus"
            variant="outlined"
            class="text-primary"
            @click="emitter?.emit('showCreateExclusionDialog', null)"
          >
            {{ t("common.add") }}
          </v-btn>
        </div>
      </template>
      <template #item.type="{ item }">
        <v-list-item class="pa-0" min-width="240px">
          <template #prepend>
            <v-icon :icon="item.icon" size="26" class="mr-3" />
          </template>
          <span class="font-weight-medium">{{ item.title }}</span>
        </v-list-item>
      </template>
      <template #item.value="{ item }">
        <v-list-item class="pa-0" min-width="160px">
          <span class="font-weight-medium">{{ item.value }}</span>
        </v-list-item>
      </template>
      <template #item.actions="{ item }">
        <v-btn-group
          v-if="
            authStore.scopes.includes('platforms.write') &&
            config.CONFIG_FILE_WRITABLE
          "
          divided
          density="compact"
          variant="text"
        >
          <v-btn
            class="text-romm-red"
            size="small"
            :title="t('common.delete')"
            @click="removeExclusion(item.value, item.type)"
          >
            <v-icon>mdi-delete</v-icon>
          </v-btn>
        </v-btn-group>
      </template>
    </v-data-table-virtual>
  </template>
  <CreateExclusionDialog />
</template>
