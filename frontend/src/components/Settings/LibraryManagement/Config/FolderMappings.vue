<script setup lang="ts">
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { computed, inject, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import PlatformIcon from "@/components/common/Platform/PlatformIcon.vue";
import configApi from "@/services/api/config";
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
const loading = ref(false);

type Row = {
  fsSlug: string;
  slug?: string;
  displayName?: string;
  type: "alias" | "variant" | "auto" | null;
};

const HEADERS = [
  { title: t("settings.folder-name-header"), align: "start", key: "fsSlug" },
  { title: t("settings.romm-platform-header"), align: "start", key: "slug" },
  { title: t("settings.type-header"), align: "center", key: "type" },
  { title: "", align: "end", key: "actions", sortable: false },
] as const;

const mappings = computed<Row[]>(() => {
  const result: Row[] = [];
  const folders = heartbeat.value?.FILESYSTEM?.FS_PLATFORMS || [];
  const bindings = config.value.PLATFORMS_BINDING || {};
  const versions = config.value.PLATFORMS_VERSIONS || {};
  const autoSlugByFs: Record<string, string | undefined> = {};

  for (const p of supportedPlatforms.value) {
    autoSlugByFs[p.slug] = p.slug;
  }

  for (const folder of folders) {
    if (bindings[folder]) {
      const slug = bindings[folder];
      const platform = supportedPlatforms.value.find((p) => p.slug === slug);
      const displayName = platform?.display_name || platform?.name || slug;
      result.push({ fsSlug: folder, slug, displayName, type: "alias" });
      continue;
    }
    if (versions[folder]) {
      const slug = versions[folder];
      const platform = supportedPlatforms.value.find((p) => p.slug === slug);
      const displayName = platform?.display_name || platform?.name || slug;
      result.push({ fsSlug: folder, slug, displayName, type: "variant" });
      continue;
    }
    const auto = autoSlugByFs[folder];
    if (auto) {
      const platform = supportedPlatforms.value.find((p) => p.slug === auto);
      const displayName = platform?.display_name || platform?.name || auto;
      result.push({ fsSlug: folder, slug: auto, displayName, type: "auto" });
    } else {
      result.push({
        fsSlug: folder,
        slug: undefined,
        displayName: undefined,
        type: null,
      });
    }
  }

  return result.sort((a, b) => a.fsSlug.localeCompare(b.fsSlug));
});

async function updatePlatformMapping(
  fsSlug: string,
  newSlug: string | undefined,
  currentType: "alias" | "variant" | "auto" | null,
) {
  if (!newSlug) {
    // Delete the mapping
    try {
      loading.value = true;
      if (currentType === "alias") {
        await configApi.deletePlatformBindConfig({ fsSlug });
      } else if (currentType === "variant") {
        await configApi.deletePlatformVersionConfig({ fsSlug });
      }
      await configStore.fetchConfig();
      emitter?.emit("snackbarShow", {
        msg: t("settings.platform-mapping-deleted"),
        icon: "mdi-check-circle",
        color: "green",
        timeout: 2000,
      });
    } catch (e: any) {
      const { response, message } = e || {};
      emitter?.emit("snackbarShow", {
        msg: t("settings.unable-to-delete-platform-mapping", {
          detail: response?.data?.detail || response?.statusText || message,
        }),
        icon: "mdi-close-circle",
        color: "red",
        timeout: 4000,
      });
    } finally {
      loading.value = false;
    }
  } else if (currentType === null) {
    // Create new alias mapping by default for null-type rows
    try {
      loading.value = true;
      await configApi.addPlatformBindConfig({ fsSlug, slug: newSlug });
      await configStore.fetchConfig();
      emitter?.emit("snackbarShow", {
        msg: t("settings.platform-mapping-created"),
        icon: "mdi-check-circle",
        color: "green",
        timeout: 2000,
      });
    } catch (e: any) {
      const { response, message } = e || {};
      emitter?.emit("snackbarShow", {
        msg: t("settings.unable-to-create-platform-mapping", {
          detail: response?.data?.detail || response?.statusText || message,
        }),
        icon: "mdi-close-circle",
        color: "red",
        timeout: 4000,
      });
    } finally {
      loading.value = false;
    }
  } else if (currentType === "auto") {
    // Convert auto-detected to explicit alias mapping
    try {
      loading.value = true;
      await configApi.addPlatformBindConfig({ fsSlug, slug: newSlug });
      await configStore.fetchConfig();
      emitter?.emit("snackbarShow", {
        msg: t("settings.platform-mapping-updated"),
        icon: "mdi-check-circle",
        color: "green",
        timeout: 2000,
      });
    } catch (e: any) {
      const { response, message } = e || {};
      emitter?.emit("snackbarShow", {
        msg: t("settings.unable-to-update-platform-mapping", {
          detail: response?.data?.detail || response?.statusText || message,
        }),
        icon: "mdi-close-circle",
        color: "red",
        timeout: 4000,
      });
    } finally {
      loading.value = false;
    }
  } else if (currentType === "alias") {
    // Update existing alias mapping to different platform
    try {
      loading.value = true;
      await configApi.deletePlatformBindConfig({ fsSlug });
      await configApi.addPlatformBindConfig({ fsSlug, slug: newSlug });
      await configStore.fetchConfig();
      emitter?.emit("snackbarShow", {
        msg: t("settings.platform-mapping-updated"),
        icon: "mdi-check-circle",
        color: "green",
        timeout: 2000,
      });
    } catch (e: any) {
      const { response, message } = e || {};
      emitter?.emit("snackbarShow", {
        msg: t("settings.unable-to-update-platform-mapping", {
          detail: response?.data?.detail || response?.statusText || message,
        }),
        icon: "mdi-close-circle",
        color: "red",
        timeout: 4000,
      });
    } finally {
      loading.value = false;
    }
  } else if (currentType === "variant") {
    // Update existing variant mapping to different platform
    try {
      loading.value = true;
      await configApi.deletePlatformVersionConfig({ fsSlug });
      await configApi.addPlatformVersionConfig({ fsSlug, slug: newSlug });
      await configStore.fetchConfig();
      emitter?.emit("snackbarShow", {
        msg: t("settings.platform-mapping-updated"),
        icon: "mdi-check-circle",
        color: "green",
        timeout: 2000,
      });
    } catch (e: any) {
      const { response, message } = e || {};
      emitter?.emit("snackbarShow", {
        msg: t("settings.unable-to-update-platform-mapping", {
          detail: response?.data?.detail || response?.statusText || message,
        }),
        icon: "mdi-close-circle",
        color: "red",
        timeout: 4000,
      });
    } finally {
      loading.value = false;
    }
  }
}

async function updateMappingType(
  fsSlug: string,
  newType: "alias" | "variant" | null,
  currentSlug: string | undefined,
) {
  if (!currentSlug || !newType) return;

  try {
    loading.value = true;

    // Delete old mapping first
    const currentType = mappings.value.find((r) => r.fsSlug === fsSlug)?.type;
    if (currentType === "alias") {
      await configApi.deletePlatformBindConfig({ fsSlug });
    } else if (currentType === "variant") {
      await configApi.deletePlatformVersionConfig({ fsSlug });
    }

    // Create new mapping with new type
    if (newType === "alias") {
      await configApi.addPlatformBindConfig({ fsSlug, slug: currentSlug });
    } else if (newType === "variant") {
      await configApi.addPlatformVersionConfig({ fsSlug, slug: currentSlug });
    }

    await configStore.fetchConfig();
    emitter?.emit("snackbarShow", {
      msg: t("settings.platform-mapping-updated"),
      icon: "mdi-check-circle",
      color: "green",
      timeout: 2000,
    });
  } catch (e: any) {
    const { response, message } = e || {};
    emitter?.emit("snackbarShow", {
      msg: t("settings.unable-to-update-platform-mapping", {
        detail: response?.data?.detail || response?.statusText || message,
      }),
      icon: "mdi-close-circle",
      color: "red",
      timeout: 4000,
    });
  } finally {
    loading.value = false;
  }
}

onMounted(async () => {
  loading.value = true;
  await platformApi
    .getSupportedPlatforms()
    .then(({ data }) => {
      supportedPlatforms.value = data || [];
    })
    .catch((e: any) => {
      const { response, message } = e || {};
      emitter?.emit("snackbarShow", {
        msg: t("settings.unable-to-get-supported-platforms", {
          detail: response?.data?.detail || response?.statusText || message,
        }),
        icon: "mdi-close-circle",
        color: "red",
        timeout: 4000,
      });
    })
    .finally(() => {
      loading.value = false;
    });
});
</script>

<template>
  <template v-if="loading">
    <v-skeleton-loader
      type="table-heading, table-tbody, table-tbody, table-row"
    />
  </template>
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
      :items="mappings"
      :sort-by="[{ key: 'fsSlug', order: 'asc' }]"
      fixed-header
      density="comfortable"
      class="rounded bg-background"
      hide-default-footer
    >
      <template #header.actions>
        <div class="d-flex align-center flex-nowrap justify-end">
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
        </div>
      </template>
      <template #item.fsSlug="{ item }">
        <v-list-item class="pa-0 font-weight-medium" min-width="150px">
          {{ item.fsSlug }}
        </v-list-item>
      </template>
      <template #item.slug="{ item }">
        <v-menu
          v-if="
            authStore.scopes.includes('platforms.write') &&
            config.CONFIG_FILE_WRITABLE
          "
        >
          <template #activator="{ props }">
            <v-list-item
              v-bind="props"
              class="pa-3 ma-1 cursor-pointer"
              min-width="250px"
            >
              <template v-if="item.slug" #prepend>
                <PlatformIcon :size="28" :slug="item.slug" class="mr-2" />
              </template>
              <span v-if="item.slug">{{ item.displayName }}</span>
              <span v-else class="text-romm-gray">—</span>
              <template #append>
                <v-icon size="small" class="ml-2">mdi-chevron-down</v-icon>
              </template>
            </v-list-item>
          </template>
          <v-list density="compact">
            <v-list-item
              v-for="platform in supportedPlatforms"
              :key="platform.slug"
              @click="
                updatePlatformMapping(item.fsSlug, platform.slug, item.type)
              "
            >
              <template #prepend>
                <PlatformIcon :size="24" :slug="platform.slug" class="mr-2" />
              </template>
              <v-list-item-title>{{ platform.display_name }}</v-list-item-title>
            </v-list-item>
            <v-divider v-if="item.slug" class="my-1" />
            <v-list-item
              v-if="item.slug"
              class="text-romm-red"
              @click="updatePlatformMapping(item.fsSlug, undefined, item.type)"
            >
              <v-icon class="mr-2">mdi-delete</v-icon>
              <v-list-item-title>{{ t("common.delete") }}</v-list-item-title>
            </v-list-item>
          </v-list>
        </v-menu>
        <v-list-item v-else class="pa-0" min-width="160px">
          <template v-if="item.slug" #prepend>
            <PlatformIcon :size="28" :slug="item.slug" class="mr-2" />
          </template>
          <span v-if="item.slug">{{ item.displayName }}</span>
          <span v-else class="text-romm-gray">—</span>
        </v-list-item>
      </template>
      <template #item.type="{ item }">
        <v-menu
          v-if="
            authStore.scopes.includes('platforms.write') &&
            item.slug &&
            config.CONFIG_FILE_WRITABLE
          "
          location="center"
        >
          <template #activator="{ props }">
            <div class="d-flex align-center justify-center">
              <v-chip
                v-if="item.type === 'alias' || item.type === 'variant'"
                v-bind="props"
                :color="item.type === 'alias' ? 'primary' : 'accent'"
                size="small"
                label
                class="cursor-pointer"
                append-icon="mdi-chevron-down"
              >
                {{
                  item.type === "alias"
                    ? t("settings.folder-alias")
                    : t("settings.platform-variant")
                }}
              </v-chip>
              <v-chip
                v-else-if="item.type === 'auto'"
                v-bind="props"
                color="romm-green"
                variant="tonal"
                size="small"
                label
                class="cursor-pointer"
                append-icon="mdi-chevron-down"
              >
                {{ t("settings.auto-detected") }}
              </v-chip>
            </div>
          </template>
          <v-list density="compact">
            <v-list-item
              @click="updateMappingType(item.fsSlug, 'alias', item.slug)"
            >
              <v-chip color="primary" size="small" label>
                {{ t("settings.folder-alias") }}
              </v-chip>
            </v-list-item>
            <v-list-item
              @click="updateMappingType(item.fsSlug, 'variant', item.slug)"
            >
              <v-chip color="accent" size="small" label>
                {{ t("settings.platform-variant") }}
              </v-chip>
            </v-list-item>
          </v-list>
        </v-menu>
      </template>
      <template #item.actions="{ item }">
        <div
          v-if="
            authStore.scopes.includes('platforms.write') &&
            config.CONFIG_FILE_WRITABLE &&
            item.type !== 'auto' &&
            item.slug
          "
        >
          <v-btn
            class="text-romm-red"
            size="small"
            variant="text"
            :title="t('common.delete')"
            @click="updatePlatformMapping(item.fsSlug, undefined, item.type)"
          >
            <v-icon>mdi-delete</v-icon>
          </v-btn>
        </div>
      </template>
    </v-data-table-virtual>
  </template>
</template>
