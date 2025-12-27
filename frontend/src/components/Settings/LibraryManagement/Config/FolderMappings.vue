<script setup lang="ts">
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { computed, inject, ref } from "vue";
import { useI18n } from "vue-i18n";
import CreateFolderMappingDialog from "@/components/Settings/LibraryManagement/Config/Dialog/CreateFolderMapping.vue";
import DeleteFolderMappingDialog from "@/components/Settings/LibraryManagement/Config/Dialog/DeleteFolderMapping.vue";
import PlatformIcon from "@/components/common/Platform/PlatformIcon.vue";
import RSection from "@/components/common/RSection.vue";
import storeAuth from "@/stores/auth";
import storeConfig from "@/stores/config";
import type { Events } from "@/types/emitter";

const { t } = useI18n();
const mappingSearch = ref("");
const emitter = inject<Emitter<Events>>("emitter");
const authStore = storeAuth();
const configStore = storeConfig();
const { config } = storeToRefs(configStore);

const HEADERS = [
  {
    title: t("settings.folder-name-header"),
    align: "start",
    sortable: true,
    key: "fsSlug",
  },
  {
    title: t("settings.romm-platform-header"),
    align: "start",
    sortable: true,
    key: "slug",
  },
  {
    title: t("settings.type-header"),
    align: "center",
    sortable: true,
    key: "type",
  },
  { title: "", align: "end", key: "actions", sortable: false },
] as const;

// Combine both bindings and versions into a single mapping list
const allMappings = computed(() => {
  const mappings: Array<{
    fsSlug: string;
    slug: string;
    type: "alias" | "variant";
  }> = [];
  const seenFolders = new Set<string>();

  // Add all bindings (aliases)
  // Note: PLATFORMS_BINDING and PLATFORMS_VERSIONS should not have overlapping fsSlug keys
  Object.entries(config.value.PLATFORMS_BINDING).forEach(([fsSlug, slug]) => {
    if (!Object.keys(config.value.PLATFORMS_VERSIONS).includes(fsSlug)) {
      mappings.push({ fsSlug, slug, type: "alias" });
      seenFolders.add(fsSlug);
    }
  });

  // Add all versions (variants)
  Object.entries(config.value.PLATFORMS_VERSIONS).forEach(([fsSlug, slug]) => {
    // Additional validation: skip if fsSlug somehow exists in both configs
    if (!seenFolders.has(fsSlug)) {
      mappings.push({ fsSlug, slug, type: "variant" });
      seenFolders.add(fsSlug);
    }
  });

  return mappings.sort((a, b) => a.fsSlug.localeCompare(b.fsSlug));
});

function editMapping(mapping: (typeof allMappings.value)[0]) {
  emitter?.emit("showCreateFolderMappingDialog", {
    fsSlug: mapping.fsSlug,
    slug: mapping.slug,
    type: mapping.type,
  });
}

function deleteMapping(mapping: (typeof allMappings.value)[0]) {
  emitter?.emit("showDeleteFolderMappingDialog", {
    fsSlug: mapping.fsSlug,
    slug: mapping.slug,
    type: mapping.type,
  });
}
</script>

<template>
  <RSection
    icon="mdi-folder-cog"
    :title="t('settings.folder-mappings')"
    class="mt-2"
  >
    <template #toolbar-title-append>
      <v-tooltip bottom max-width="500">
        <template #activator="{ props }">
          <v-btn
            v-bind="props"
            size="small"
            variant="text"
            icon="mdi-information-outline"
          />
        </template>
        <div>
          <p class="mb-2">
            <strong>{{ t("settings.folder-alias") }}:</strong>
            {{ t("settings.folder-mappings-tooltip-aliases") }}
          </p>
          <p>
            <strong>{{ t("settings.platform-variant") }}:</strong>
            {{ t("settings.folder-mappings-tooltip-variants") }}
          </p>
        </div>
      </v-tooltip>
    </template>
    <template #content>
      <v-text-field
        v-model="mappingSearch"
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
        :style="{ 'max-height': '40dvh' }"
        :search="mappingSearch"
        :headers="HEADERS"
        :items="allMappings"
        :sort-by="[{ key: 'fsSlug', order: 'asc' }]"
        fixed-header
        fixed-footer
        density="comfortable"
        class="rounded bg-background"
        hide-default-footer
      >
        <template #header.actions>
          <v-btn
            v-if="authStore.scopes.includes('platforms.write')"
            prepend-icon="mdi-plus"
            variant="outlined"
            class="text-primary"
            @click="emitter?.emit('showCreateFolderMappingDialog', null)"
          >
            {{ t("common.add") }}
          </v-btn>
        </template>
        <template #item.fsSlug="{ item }">
          <v-list-item class="pa-0 font-weight-medium" min-width="120px">
            {{ item.fsSlug }}
          </v-list-item>
        </template>
        <template #item.slug="{ item }">
          <v-list-item class="pa-0" min-width="120px">
            <template #prepend>
              <PlatformIcon :size="30" :slug="item.slug" class="mr-2" />
            </template>
            {{ item.slug }}
          </v-list-item>
        </template>
        <template #item.type="{ item }">
          <v-chip
            :color="item.type === 'alias' ? 'primary' : 'accent'"
            size="small"
            label
            density="compact"
          >
            {{
              item.type === "alias"
                ? t("settings.folder-alias")
                : t("settings.platform-variant")
            }}
          </v-chip>
        </template>
        <template #item.actions="{ item }">
          <v-btn-group divided density="compact" variant="text">
            <v-btn
              v-if="authStore.scopes.includes('platforms.write')"
              size="small"
              :title="t('common.edit')"
              @click="editMapping(item)"
            >
              <v-icon>mdi-pencil</v-icon>
            </v-btn>
            <v-btn
              v-if="authStore.scopes.includes('platforms.write')"
              class="text-romm-red"
              size="small"
              @click="deleteMapping(item)"
            >
              <v-icon>mdi-delete</v-icon>
            </v-btn>
          </v-btn-group>
        </template>
      </v-data-table-virtual>
    </template>
  </RSection>

  <CreateFolderMappingDialog />
  <DeleteFolderMappingDialog />
</template>
