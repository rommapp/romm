<script setup lang="ts">
import { useLocalStorage } from "@vueuse/core";
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { computed, inject, onBeforeUnmount, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import RDialog from "@/components/common/RDialog.vue";
import socket from "@/services/socket";
import storeConfig from "@/stores/config";
import storeHeartbeat, { type MetadataOption } from "@/stores/heartbeat";
import { type SimpleRom } from "@/stores/roms";
import storeScanning from "@/stores/scanning";
import type { Events } from "@/types/emitter";

const LOCAL_STORAGE_METADATA_SOURCES_KEY = "scan.metadataSources";
const LOCAL_STORAGE_LAUNCHBOX_REMOTE_ENABLED_KEY =
  "scan.launchboxRemoteEnabled";

const { t } = useI18n();
const emitter = inject<Emitter<Events>>("emitter");
const show = ref(false);
const rom = ref<SimpleRom | null>(null);
const heartbeat = storeHeartbeat();
const scanningStore = storeScanning();
const configStore = storeConfig();
const { config } = storeToRefs(configStore);

const calculateHashes = computed(() => !config.value.SKIP_HASH_CALCULATION);

const metadataOptions = computed(() => {
  return heartbeat.getMetadataOptionsByPriority().map((option) => {
    // Check if option requires hashes but hash calculation is disabled
    const requiresHashes =
      option.value === "hasheous" ||
      option.value === "ra" ||
      option.value === "playmatch";
    const hashingDisabled = !calculateHashes.value;
    const disabled =
      hashingDisabled && requiresHashes
        ? t("scan.requires-hashes", { source: option.name })
        : option.disabled;

    return {
      ...option,
      disabled,
    };
  });
});

const storedMetadataSources = useLocalStorage(
  LOCAL_STORAGE_METADATA_SOURCES_KEY,
  [] as string[],
);
const launchboxRemoteEnabled = useLocalStorage(
  LOCAL_STORAGE_LAUNCHBOX_REMOTE_ENABLED_KEY,
  true,
);

const metadataSources = ref<MetadataOption[]>([]);
const isLaunchboxSelected = computed(() =>
  metadataSources.value.some((s) => s.value === "launchbox"),
);

watch(
  [metadataOptions, storedMetadataSources],
  ([newOptions, newStoredMetadataSources]) => {
    const filteredMetadataSources = newOptions.filter(
      (option) =>
        newStoredMetadataSources.includes(option.value) && !option.disabled,
    );
    metadataSources.value =
      filteredMetadataSources.length > 0
        ? filteredMetadataSources
        : heartbeat.getEnabledMetadataOptions();
  },
  { immediate: true },
);

const scanOptions = computed(() => [
  {
    title: t("scan.unmatched-games"),
    subtitle: t("scan.unmatched-games-desc"),
    value: "unmatched",
  },
  {
    title: t("scan.update-metadata"),
    subtitle: t("scan.update-metadata-desc"),
    value: "update",
  },
  {
    title: t("scan.hashes"),
    subtitle: t("scan.hashes-desc"),
    value: "hashes",
  },
  {
    title: t("scan.complete-rescan"),
    subtitle: t("scan.complete-rescan-desc"),
    value: "complete",
  },
]);
const scanType = ref("unmatched");

const handleShowRefreshMetadataDialog = (romToRefresh: SimpleRom) => {
  rom.value = romToRefresh;
  show.value = true;
};
emitter?.on("showRefreshMetadataDialog", handleShowRefreshMetadataDialog);

onBeforeUnmount(() => {
  emitter?.off("showRefreshMetadataDialog", handleShowRefreshMetadataDialog);
});

async function onScan() {
  if (!rom.value) return;

  scanningStore.setScanning(true);

  // Store selected meta sources in storage
  storedMetadataSources.value = metadataSources.value.map((s) => s.value);

  emitter?.emit("snackbarShow", {
    msg: `Refreshing ${rom.value.name ?? rom.value.fs_name} metadata...`,
    icon: "mdi-loading mdi-spin",
    color: "primary",
  });

  if (!socket.connected) socket.connect();
  socket.emit("scan", {
    platforms: [rom.value.platform_id],
    roms_ids: [rom.value.id],
    type: scanType.value,
    apis: metadataSources.value.map((s) => s.value),
    launchbox_remote_enabled: launchboxRemoteEnabled.value,
  });

  closeDialog();
}

function closeDialog() {
  show.value = false;
  rom.value = null;
}
</script>

<template>
  <RDialog
    v-model="show"
    icon="mdi-magnify-scan"
    :width="'500px'"
    @close="closeDialog"
  >
    <template #header>
      <v-toolbar-title class="text-h6 ml-2">
        {{ t("rom.refresh-metadata") }}
      </v-toolbar-title>
    </template>

    <template #content>
      <v-row class="pa-4" no-gutters>
        <v-col cols="12" class="mb-4">
          <span class="text-body-2 text-medium-emphasis">
            {{ rom?.name ?? rom?.fs_name }}
          </span>
        </v-col>

        <!-- Metadata sources -->
        <v-col cols="12" class="mb-4">
          <v-select
            v-model="metadataSources"
            :items="metadataOptions"
            :label="t('scan.metadata-sources')"
            item-title="name"
            prepend-inner-icon="mdi-database-search"
            variant="outlined"
            density="comfortable"
            multiple
            return-object
            clearable
            hide-details
            chips
          >
            <template #item="{ props, item }">
              <v-list-item
                v-bind="props"
                :title="item.raw.name"
                :subtitle="item.raw.disabled"
                :disabled="Boolean(item.raw.disabled)"
              >
                <template #prepend>
                  <v-avatar size="25" rounded="1">
                    <v-img :src="item.raw.logo_path" />
                  </v-avatar>
                </template>

                <template v-if="item.raw.value === 'launchbox'" #append>
                  <div class="d-flex align-center">
                    <span
                      class="text-caption text-primary text-medium-emphasis mr-4"
                      :class="{ 'text-romm-gray': launchboxRemoteEnabled }"
                    >
                      Local
                    </span>
                    <v-switch
                      v-model="launchboxRemoteEnabled"
                      color="primary"
                      density="compact"
                      hide-details
                      :disabled="!isLaunchboxSelected"
                      @click.stop
                      @mousedown.stop
                    />
                    <span
                      class="text-caption text-primary text-medium-emphasis ml-4"
                      :class="{ 'text-romm-gray': !launchboxRemoteEnabled }"
                    >
                      Cloud
                    </span>
                  </div>
                </template>
              </v-list-item>
            </template>
            <template #chip="{ item }">
              <v-avatar class="mx-1" size="24" rounded="1">
                <v-img :src="item.raw.logo_path" />
              </v-avatar>
            </template>
          </v-select>
        </v-col>

        <!-- Scan type -->
        <v-col cols="12">
          <v-select
            v-model="scanType"
            :items="scanOptions"
            :label="t('scan.scan-options')"
            prepend-inner-icon="mdi-magnify-scan"
            hide-details
            density="comfortable"
            variant="outlined"
          >
            <template #item="{ props, item }">
              <v-list-item v-bind="props" :subtitle="item.raw.subtitle" />
            </template>
            <template #append-inner>
              <v-menu open-on-hover location="bottom start">
                <template #activator="{ props }">
                  <v-icon
                    v-bind="props"
                    icon="mdi-information-outline"
                    size="small"
                    class="ml-2"
                    @click.stop
                  />
                </template>
                <v-card max-width="600">
                  <v-card-text>
                    <div v-html="t('scan.scan-types-info')" />
                    <div class="mt-3 text-right">
                      <a
                        href="https://docs.romm.app/latest/Usage/LibraryManagement/#scan"
                        target="_blank"
                        rel="noopener"
                        style="font-style: italic; text-decoration: underline"
                      >
                        {{ t("scan.scan-types-more-info") }}
                      </a>
                    </div>
                  </v-card-text>
                </v-card>
              </v-menu>
            </template>
          </v-select>
        </v-col>
      </v-row>
    </template>

    <template #footer>
      <v-row class="justify-end pa-2" no-gutters>
        <v-btn variant="text" @click="closeDialog">
          {{ t("common.cancel") }}
        </v-btn>
        <v-btn
          :disabled="metadataSources.length === 0"
          color="primary"
          class="ml-2"
          @click="onScan"
        >
          <template #prepend>
            <v-icon icon="mdi-magnify-scan" />
          </template>
          {{ t("rom.refresh-metadata") }}
        </v-btn>
      </v-row>
    </template>
  </RDialog>
</template>
