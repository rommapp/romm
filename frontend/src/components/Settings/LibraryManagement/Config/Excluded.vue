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

const DEFAULT_LIST_MAP: Record<
  string,
  | "DEFAULT_EXCLUDED_DIRS"
  | "DEFAULT_EXCLUDED_FILES"
  | "DEFAULT_EXCLUDED_EXTENSIONS"
> = {
  EXCLUDED_PLATFORMS: "DEFAULT_EXCLUDED_DIRS",
  EXCLUDED_SINGLE_FILES: "DEFAULT_EXCLUDED_FILES",
  EXCLUDED_SINGLE_EXT: "DEFAULT_EXCLUDED_EXTENSIONS",
  EXCLUDED_MULTI_FILES: "DEFAULT_EXCLUDED_DIRS",
  EXCLUDED_MULTI_PARTS_FILES: "DEFAULT_EXCLUDED_FILES",
  EXCLUDED_MULTI_PARTS_EXT: "DEFAULT_EXCLUDED_EXTENSIONS",
};

const EXCLUSION_DEFS = [
  {
    key: "EXCLUDED_PLATFORMS" as const,
    title: () => t("common.platform"),
    icon: "mdi-gamepad-variant-outline",
  },
  {
    key: "EXCLUDED_SINGLE_FILES" as const,
    title: () => t("settings.excluded-single-rom-files"),
    icon: "mdi-file-remove-outline",
  },
  {
    key: "EXCLUDED_SINGLE_EXT" as const,
    title: () => t("settings.excluded-single-rom-extensions"),
    icon: "mdi-file-code-outline",
  },
  {
    key: "EXCLUDED_MULTI_FILES" as const,
    title: () => t("settings.excluded-multi-rom-files"),
    icon: "mdi-file-multiple-outline",
  },
  {
    key: "EXCLUDED_MULTI_PARTS_FILES" as const,
    title: () => t("settings.excluded-multi-rom-parts-files"),
    icon: "mdi-folder-multiple-outline",
  },
  {
    key: "EXCLUDED_MULTI_PARTS_EXT" as const,
    title: () => t("settings.excluded-multi-rom-parts-extensions"),
    icon: "mdi-file-cog-outline",
  },
];

function isDefault(type: string, value: string): boolean {
  const defaultKey = DEFAULT_LIST_MAP[type];
  if (!defaultKey) return false;
  const defaults = config.value[defaultKey] || [];
  return defaults.includes(value);
}

const exclusions = computed<Row[]>(() => {
  const result: Row[] = [];
  for (const def of EXCLUSION_DEFS) {
    const set = config.value[def.key] || [];
    for (const v of set) {
      if (!isDefault(def.key, v)) {
        result.push({
          type: def.key,
          title: def.title(),
          icon: def.icon,
          value: v,
        });
      }
    }
  }
  return result.sort(
    (a, b) => a.title.localeCompare(b.title) || a.value.localeCompare(b.value),
  );
});

const defaultExclusions = computed<Row[]>(() => {
  const seen = new Map<string, Row>();
  for (const def of EXCLUSION_DEFS) {
    const set = config.value[def.key] || [];
    for (const v of set) {
      if (isDefault(def.key, v) && !seen.has(v)) {
        seen.set(v, {
          type: def.key,
          title: def.title(),
          icon: def.icon,
          value: v,
        });
      }
    }
  }
  return [...seen.values()].sort((a, b) => a.value.localeCompare(b.value));
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
  <div v-if="exclusions.length === 0" class="text-center py-8">
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
      :items="exclusions"
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

  <div v-if="defaultExclusions.length > 0" class="mt-6">
    <div class="text-subtitle-2 text-romm-gray mb-2">
      {{ t("settings.exclusions-defaults") }}
    </div>
    <v-row dense>
      <v-col
        v-for="item in defaultExclusions"
        :key="item.value"
        cols="12"
        sm="6"
        lg="3"
      >
        <div class="d-flex align-center">
          <v-icon :icon="item.icon" size="20" class="mr-2 opacity-50" />
          <div>
            <div class="text-body-2 opacity-70">{{ item.value }}</div>
            <div class="text-caption opacity-50">{{ item.title }}</div>
          </div>
        </div>
      </v-col>
    </v-row>
  </div>

  <CreateExclusionDialog />
</template>
