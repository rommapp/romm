<script setup lang="ts">
import { isUndefined } from "lodash";
import { computed, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import storeHeartbeat from "@/stores/heartbeat";

const { t } = useI18n();
const heartbeat = storeHeartbeat();

const heartbeatStatus = ref<Record<string, boolean | undefined>>({
  igdb: undefined,
  moby: undefined,
  ss: undefined,
  ra: undefined,
  hasheous: undefined,
  lb: undefined,
  flashpoint: undefined,
  hltb: undefined,
  sgdb: undefined,
});

// Use a computed property to reactively update metadataOptions based on heartbeat
const metadataOptions = computed(() => [
  {
    name: "IGDB",
    value: "igdb",
    logo_path: "/assets/scrappers/igdb.png",
    disabled: !heartbeat.value.METADATA_SOURCES?.IGDB_API_ENABLED,
    heartbeat: heartbeatStatus.value.igdb,
  },
  {
    name: "MobyGames",
    value: "moby",
    logo_path: "/assets/scrappers/moby.png",
    disabled: !heartbeat.value.METADATA_SOURCES?.MOBY_API_ENABLED,
    heartbeat: heartbeatStatus.value.moby,
  },
  {
    name: "ScreenScrapper",
    value: "ss",
    logo_path: "/assets/scrappers/ss.png",
    disabled: !heartbeat.value.METADATA_SOURCES?.SS_API_ENABLED,
    heartbeat: heartbeatStatus.value.ss,
  },
  {
    name: "RetroAchievements",
    value: "ra",
    logo_path: "/assets/scrappers/ra.png",
    disabled: !heartbeat.value.METADATA_SOURCES?.RA_API_ENABLED,
    heartbeat: heartbeatStatus.value.ra,
  },
  {
    name: "Hasheous",
    value: "hasheous",
    logo_path: "/assets/scrappers/hasheous.png",
    disabled: !heartbeat.value.METADATA_SOURCES?.HASHEOUS_API_ENABLED,
    heartbeat: heartbeatStatus.value.hasheous,
  },
  {
    name: "Launchbox",
    value: "lb",
    logo_path: "/assets/scrappers/launchbox.png",
    disabled: !heartbeat.value.METADATA_SOURCES?.LAUNCHBOX_API_ENABLED,
    heartbeat: heartbeatStatus.value.lb,
  },
  {
    name: "Flashpoint Project",
    value: "flashpoint",
    logo_path: "/assets/scrappers/flashpoint.png",
    disabled: !heartbeat.value.METADATA_SOURCES?.FLASHPOINT_API_ENABLED,
    heartbeat: heartbeatStatus.value.flashpoint,
  },
  {
    name: "HowLongToBeat",
    value: "hltb",
    logo_path: "/assets/scrappers/hltb.png",
    disabled: !heartbeat.value.METADATA_SOURCES?.HLTB_API_ENABLED,
    heartbeat: heartbeatStatus.value.hltb,
  },
  {
    name: "SteamgridDB",
    value: "sgdb",
    logo_path: "/assets/scrappers/sgdb.png",
    disabled: !heartbeat.value.METADATA_SOURCES?.STEAMGRIDDB_API_ENABLED,
    heartbeat: heartbeatStatus.value.sgdb,
  },
]);

// Fetch heartbeat status for all metadata sources in parallel
async function fetchAllHeartbeats() {
  Promise.all(
    metadataOptions.value
      .filter((source) => !source.disabled)
      .map(async (source) => {
        const result = await heartbeat.fetchMetadataHeartbeat(source.value);
        heartbeatStatus.value[source.value] = result;
      }),
  );
}

onMounted(() => {
  fetchAllHeartbeats();
});
</script>

<template>
  <v-row no-gutters class="pa-2">
    <v-col cols="12">
      <v-card class="pa-4">
        <v-card-title class="text-h5 mb-4">
          <v-icon class="mr-2">mdi-database-cog</v-icon>
          {{ t("scan.metadata-sources") }}
        </v-card-title>

        <v-card-text>
          <p class="text-body-1 mb-4">
            {{ t("settings.metadata-sources-description") }}
          </p>

          <v-list class="bg-transparent">
            <v-list-item
              v-for="source in metadataOptions"
              :key="source.value"
              class="text-white text-shadow mb-2"
              :title="source.name"
              :subtitle="
                source.disabled
                  ? t('settings.api-key-missing-or-invalid')
                  : t('settings.api-key-valid')
              "
            >
              <template #prepend>
                <v-avatar size="40" rounded="1">
                  <v-img :src="source.logo_path" />
                </v-avatar>
              </template>
              <template #append>
                <div class="d-flex align-center gap-2">
                  <!-- Heartbeat status indicator -->
                  <v-chip
                    v-if="!source.disabled"
                    :color="
                      source.heartbeat === true
                        ? 'success'
                        : source.heartbeat === false
                          ? 'error'
                          : 'warning'
                    "
                    :variant="source.heartbeat === undefined ? 'tonal' : 'flat'"
                    size="small"
                  >
                    <v-icon
                      :icon="
                        source.heartbeat === true
                          ? 'mdi-heart-pulse'
                          : source.heartbeat === false
                            ? 'mdi-heart-broken'
                            : 'mdi-loading'
                      "
                      class="mr-1"
                      size="small"
                      :class="{ 'mdi-spin': source.heartbeat === undefined }"
                    />
                    {{
                      source.heartbeat
                        ? t("common.connected")
                        : isUndefined(source.heartbeat)
                          ? t("common.checking")
                          : t("common.disconnected")
                    }}
                  </v-chip>

                  <!-- Enabled/Disabled status -->
                  <v-chip
                    :color="source.disabled ? 'error' : 'success'"
                    :variant="source.disabled ? 'tonal' : 'flat'"
                    size="small"
                  >
                    <v-icon
                      :icon="source.disabled ? 'mdi-close' : 'mdi-check'"
                      class="mr-1"
                      size="small"
                    />
                    {{
                      source.disabled
                        ? t("common.disabled")
                        : t("common.enabled")
                    }}
                  </v-chip>
                </div>
              </template>
            </v-list-item>
          </v-list>
        </v-card-text>
      </v-card>
    </v-col>
  </v-row>
</template>
