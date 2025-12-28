<script setup lang="ts">
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { computed, inject, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import CreateFolderMappingDialog from "@/components/Settings/LibraryManagement/Config/Dialog/CreateFolderMapping.vue";
import DeleteFolderMappingDialog from "@/components/Settings/LibraryManagement/Config/Dialog/DeleteFolderMapping.vue";
import PlatformIcon from "@/components/common/Platform/PlatformIcon.vue";
import RSection from "@/components/common/RSection.vue";
import platformApi from "@/services/api/platform";
import storeAuth from "@/stores/auth";
import storeConfig from "@/stores/config";
import storeHeartbeat from "@/stores/heartbeat";
import type { Platform } from "@/stores/platforms";
import type { Events } from "@/types/emitter";

const { t } = useI18n();
const emitter = inject<Emitter<Events>>("emitter");
const authStore = storeAuth();
const configStore = storeConfig();
const { config } = storeToRefs(configStore);
const heartbeat = storeHeartbeat();
const supportedPlatforms = ref<Platform[]>([]);
const search = ref("");

onMounted(async () => {
  try {
    const { data } = await platformApi.getSupportedPlatforms();
    supportedPlatforms.value = (data || []).sort((a, b) =>
      a.name.localeCompare(b.name),
    );
  } catch (e: any) {
    const { response, message } = e || {};
    emitter?.emit("snackbarShow", {
      msg: `Unable to get supported platforms: ${
        response?.data?.detail || response?.statusText || message
      }`,
      icon: "mdi-close-circle",
      color: "red",
      timeout: 4000,
    });
  }
});

type Row = {
  fsSlug: string;
  slug?: string;
  type: "alias" | "variant" | "auto" | null;
};

const HEADERS = [
  { title: t("settings.folder-name-header"), align: "start", key: "fsSlug" },
  { title: t("settings.romm-platform-header"), align: "start", key: "slug" },
  { title: t("settings.type-header"), align: "center", key: "type" },
  { title: "", align: "end", key: "actions", sortable: false },
] as const;

const rows = computed<Row[]>(() => {
  const folders = heartbeat.value?.FILESYSTEM?.FS_PLATFORMS || [];
  const result: Row[] = [];

  const bindings = config.value.PLATFORMS_BINDING || {};
  const versions = config.value.PLATFORMS_VERSIONS || {};

  const autoSlugByFs: Record<string, string | undefined> = {};
  for (const p of supportedPlatforms.value) {
    if (p?.fs_slug) autoSlugByFs[p.fs_slug] = p.slug;
    // some setups might name folders directly as slug
    autoSlugByFs[p.slug] = p.slug;
  }

  for (const fs of folders) {
    if (bindings[fs]) {
      result.push({ fsSlug: fs, slug: bindings[fs], type: "alias" });
      continue;
    }
    if (versions[fs]) {
      result.push({ fsSlug: fs, slug: versions[fs], type: "variant" });
      continue;
    }
    const auto = autoSlugByFs[fs];
    result.push({ fsSlug: fs, slug: auto, type: auto ? "auto" : null });
  }

  return result.sort((a, b) => a.fsSlug.localeCompare(b.fsSlug));
});

function addAlias(fsSlug: string) {
  emitter?.emit("showCreateFolderMappingDialog", {
    fsSlug,
    slug: "",
    type: "alias",
  });
}

function addVariant(fsSlug: string) {
  emitter?.emit("showCreateFolderMappingDialog", {
    fsSlug,
    slug: "",
    type: "variant",
  });
}

function editMapping(row: Row) {
  if (!row.slug || !row.type || row.type === "auto") return;
  emitter?.emit("showCreateFolderMappingDialog", {
    fsSlug: row.fsSlug,
    slug: row.slug,
    type: row.type,
  });
}

function deleteMapping(row: Row) {
  if (!row.slug || !row.type || row.type === "auto") return;
  emitter?.emit("showDeleteFolderMappingDialog", {
    fsSlug: row.fsSlug,
    slug: row.slug,
    type: row.type,
  });
}
</script>

<template>
  <RSection icon="mdi-folder-cog" :title="t('settings.folder-mappings')">
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
          <p class="text-caption mt-2">
            {{ t("settings.folder-mappings-mutually-exclusive") }}
          </p>
        </div>
      </v-tooltip>
    </template>
    <template #content>
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
        :style="{ 'max-height': '50dvh' }"
        :search="search"
        :headers="HEADERS"
        :items="rows"
        :sort-by="[{ key: 'fsSlug', order: 'asc' }]"
        fixed-header
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
          <v-list-item class="pa-0" min-width="160px">
            <template v-if="item.slug" #prepend>
              <PlatformIcon :size="28" :slug="item.slug" class="mr-2" />
            </template>
            <span v-if="item.slug">{{ item.slug }}</span>
            <span v-else class="text-romm-gray">—</span>
          </v-list-item>
        </template>
        <template #item.type="{ item }">
          <div class="d-flex align-center justify-center">
            <v-chip
              v-if="item.type === 'alias'"
              color="primary"
              size="small"
              label
            >
              {{ t("settings.folder-alias") }}
            </v-chip>
            <v-chip
              v-else-if="item.type === 'variant'"
              color="accent"
              size="small"
              label
            >
              {{ t("settings.platform-variant") }}
            </v-chip>
            <v-chip
              v-else-if="item.type === 'auto'"
              color="success"
              variant="tonal"
              size="small"
              label
            >
              {{ t("settings.auto-detected") }}
            </v-chip>
            <span v-else class="text-romm-gray">—</span>
          </div>
        </template>
        <template #item.actions="{ item }">
          <v-btn-group divided density="compact" variant="text">
            <v-btn
              v-if="
                authStore.scopes.includes('platforms.write') &&
                !item.type &&
                config.CONFIG_FILE_WRITABLE
              "
              size="small"
              class="text-primary"
              :title="t('settings.add-folder-alias')"
              @click="addAlias(item.fsSlug)"
            >
              <v-icon>mdi-link-variant</v-icon>
            </v-btn>
            <v-btn
              v-if="
                authStore.scopes.includes('platforms.write') &&
                !item.type &&
                config.CONFIG_FILE_WRITABLE
              "
              size="small"
              class="text-accent"
              :title="t('settings.add-platform-variant')"
              @click="addVariant(item.fsSlug)"
            >
              <v-icon>mdi-family-tree</v-icon>
            </v-btn>
            <v-btn
              v-if="
                authStore.scopes.includes('platforms.write') &&
                (item.type === 'alias' || item.type === 'variant') &&
                config.CONFIG_FILE_WRITABLE
              "
              size="small"
              :title="t('common.edit')"
              @click="editMapping(item)"
            >
              <v-icon>mdi-pencil</v-icon>
            </v-btn>
            <v-btn
              v-if="
                authStore.scopes.includes('platforms.write') &&
                (item.type === 'alias' || item.type === 'variant') &&
                config.CONFIG_FILE_WRITABLE
              "
              class="text-romm-red"
              size="small"
              :title="t('common.delete')"
              @click="deleteMapping(item)"
            >
              <v-icon>mdi-delete</v-icon>
            </v-btn>
          </v-btn-group>
        </template>
      </v-data-table-virtual>
      <CreateFolderMappingDialog />
      <DeleteFolderMappingDialog />
    </template>
  </RSection>
</template>
