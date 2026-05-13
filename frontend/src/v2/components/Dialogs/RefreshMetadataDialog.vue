<script setup lang="ts">
// RefreshMetadataDialog — kicks off a per-ROM metadata re-scan. Emits the
// same `scan` socket event as the main Scan view (ScanBtn owns the
// lifecycle socket handlers, we just emit here).
import { RBtn, RDialog, RSelect } from "@v2/lib";
import { useLocalStorage } from "@vueuse/core";
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { computed, inject, onBeforeUnmount, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import socket from "@/services/socket";
import storeConfig from "@/stores/config";
import storeHeartbeat, { type MetadataOption } from "@/stores/heartbeat";
import { type SimpleRom } from "@/stores/roms";
import storeScanning from "@/stores/scanning";
import type { Events } from "@/types/emitter";
import { useSnackbar } from "@/v2/composables/useSnackbar";

defineOptions({ inheritAttrs: false });

const LOCAL_STORAGE_METADATA_SOURCES_KEY = "scan.metadataSources";
const LOCAL_STORAGE_LAUNCHBOX_REMOTE_ENABLED_KEY =
  "scan.launchboxRemoteEnabled";

const { t } = useI18n();
const emitter = inject<Emitter<Events>>("emitter");
const snackbar = useSnackbar();
const show = ref(false);
const rom = ref<SimpleRom | null>(null);
const heartbeat = storeHeartbeat();
const scanningStore = storeScanning();
const configStore = storeConfig();
const { config } = storeToRefs(configStore);

const calculateHashes = computed(() => !config.value.SKIP_HASH_CALCULATION);

const metadataOptions = computed(() =>
  heartbeat.getMetadataOptionsByPriority().map((option) => {
    const requiresHashes = option.value === "hasheous" || option.value === "ra";
    const hashingDisabled = !calculateHashes.value;
    let disabled = option.disabled;
    if (hashingDisabled && requiresHashes) {
      if (option.value === "hasheous") {
        disabled = t("scan.hasheous-requires-hashes");
      } else if (option.value === "ra") {
        disabled = t("scan.retroachievements-requires-hashes");
      }
    }
    return { ...option, disabled };
  }),
);

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

type ScanType = "unmatched" | "update" | "hashes" | "complete";
const scanOptions = computed<
  { title: string; subtitle: string; value: ScanType }[]
>(() => [
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
const scanType = ref<ScanType>("unmatched");

const openHandler = (romToRefresh: SimpleRom) => {
  rom.value = romToRefresh;
  show.value = true;
};
emitter?.on("showRefreshMetadataDialog", openHandler);
onBeforeUnmount(() => emitter?.off("showRefreshMetadataDialog", openHandler));

function onScan() {
  if (!rom.value) return;

  scanningStore.setScanning(true);
  storedMetadataSources.value = metadataSources.value.map((s) => s.value);

  snackbar.info(
    `Refreshing ${rom.value.name ?? rom.value.fs_name} metadata...`,
    { icon: "mdi-loading mdi-spin" },
  );

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
    width="520"
    @close="closeDialog"
  >
    <template #header>
      <span>{{ t("rom.refresh-metadata") }}</span>
    </template>
    <template #content>
      <div class="r-v2-refresh">
        <p v-if="rom" class="r-v2-refresh__rom">
          {{ rom.name ?? rom.fs_name }}
        </p>

        <RSelect
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
          <template #item="{ props: itemProps, item }">
            <v-list-item
              v-bind="itemProps"
              :title="item.raw.name"
              :subtitle="item.raw.disabled"
              :disabled="Boolean(item.raw.disabled)"
            >
              <template #prepend>
                <v-avatar size="22" rounded="1">
                  <v-img :src="item.raw.logo_path" />
                </v-avatar>
              </template>

              <template v-if="item.raw.value === 'launchbox'" #append>
                <div class="r-v2-refresh__lb">
                  <span
                    class="text-caption"
                    :class="{ 'r-v2-refresh__lb-dim': launchboxRemoteEnabled }"
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
                    class="text-caption"
                    :class="{ 'r-v2-refresh__lb-dim': !launchboxRemoteEnabled }"
                  >
                    Cloud
                  </span>
                </div>
              </template>
            </v-list-item>
          </template>
          <template #chip="{ item }">
            <v-chip>
              <v-avatar class="mr-1" size="18" rounded="1">
                <v-img :src="item.raw.logo_path" />
              </v-avatar>
              <span>{{ item.raw.name }}</span>
            </v-chip>
          </template>
        </RSelect>

        <RSelect
          v-model="scanType"
          :items="scanOptions"
          :label="t('scan.scan-options')"
          prepend-inner-icon="mdi-magnify-scan"
          variant="outlined"
          density="comfortable"
          hide-details
        >
          <template #item="{ props: itemProps, item }">
            <v-list-item v-bind="itemProps" :subtitle="item.raw.subtitle" />
          </template>
        </RSelect>
      </div>
    </template>
    <template #footer>
      <RBtn variant="text" @click="closeDialog">
        {{ t("common.cancel") }}
      </RBtn>
      <div style="flex: 1" />
      <RBtn
        variant="translucent"
        color="primary"
        prepend-icon="mdi-magnify-scan"
        :disabled="metadataSources.length === 0"
        @click="onScan"
      >
        {{ t("rom.refresh-metadata") }}
      </RBtn>
    </template>
  </RDialog>
</template>

<style scoped>
.r-v2-refresh {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.r-v2-refresh__rom {
  margin: 0 0 4px;
  font-size: 13px;
  color: var(--r-color-brand-primary);
  font-weight: var(--r-font-weight-medium);
  text-align: center;
}

.r-v2-refresh__lb {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.r-v2-refresh__lb-dim {
  color: var(--r-color-fg-muted);
}
</style>
