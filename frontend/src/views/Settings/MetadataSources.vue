<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import RSection from "@/components/common/RSection.vue";
import storeHeartbeat from "@/stores/heartbeat";

const { t } = useI18n();
const heartbeat = storeHeartbeat();

const heartbeatStatus = ref<Record<string, boolean | undefined>>({
  igdb: undefined,
  moby: undefined,
  ss: undefined,
  ra: undefined,
  hasheous: undefined,
  launchbox: undefined,
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
    name: "ScreenScraper",
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
    value: "launchbox",
    logo_path: "/assets/scrappers/launchbox.png",
    disabled: !heartbeat.value.METADATA_SOURCES?.LAUNCHBOX_API_ENABLED,
    heartbeat: heartbeatStatus.value.launchbox,
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
  metadataOptions.value
    .filter((source) => !source.disabled)
    .map(async (source) => {
      const result = await heartbeat.fetchMetadataHeartbeat(source.value);
      heartbeatStatus.value[source.value] = result;
    });
}

// Helper function to get status text for a metadata source
function getSourceStatusText(source: {
  disabled: boolean;
  heartbeat?: boolean;
}) {
  if (source.disabled) {
    return t("scan.api-key-missing-short");
  }
  if (source.heartbeat === true) {
    return t("scan.api-key-valid");
  }
  if (source.heartbeat === false) {
    return t("scan.api-key-invalid");
  }
  return t("scan.connection-in-progress");
}

// Helper function to get tooltip text for connection status
function getConnectionStatusTooltip(source: {
  disabled: boolean;
  heartbeat?: boolean;
}) {
  if (source.disabled) {
    return t("scan.api-key-missing-or-disabled");
  }
  if (source.heartbeat === true) {
    return t("scan.connection-successful");
  }
  if (source.heartbeat === false) {
    return t("scan.connection-failed");
  }
  return t("scan.connection-in-progress");
}

onMounted(() => {
  fetchAllHeartbeats();
});
</script>

<template>
  <RSection
    icon="mdi-database-cog"
    :title="t('scan.metadata-sources')"
    class="ma-2"
  >
    <template #content>
      <v-row no-gutters class="mt-2 cols-12">
        <v-col
          v-for="source in metadataOptions"
          :key="source.value"
          cols="12"
          sm="6"
          md="4"
          lg="3"
          xl="2"
          class="pa-2"
        >
          <v-card class="pa-4 h-100 bg-toplayer" variant="elevated">
            <div class="d-flex align-center mb-3">
              <v-avatar variant="text" size="48" rounded="1" class="mr-3">
                <v-img :src="source.logo_path" />
              </v-avatar>
              <div class="flex-grow-1">
                <h3 class="text-h6 text-white">{{ source.name }}</h3>
                <p class="text-caption text-grey-lighten-1 mb-0">
                  {{ getSourceStatusText(source) }}
                </p>
              </div>
            </div>

            <v-row no-gutters class="flex justify-center">
              <v-avatar
                :color="source.disabled ? 'error' : 'success'"
                size="large"
                :title="
                  source.disabled
                    ? t('scan.api-key-missing-or-disabled')
                    : t('scan.api-key-set')
                "
              >
                <v-icon>
                  {{ source.disabled ? "mdi-key-alert" : "mdi-key" }}
                </v-icon>
              </v-avatar>
              <v-avatar
                :color="
                  source.heartbeat === true
                    ? 'success'
                    : source.heartbeat === false
                      ? 'error'
                      : source.disabled
                        ? 'surface'
                        : 'warning'
                "
                size="large"
                :title="getConnectionStatusTooltip(source)"
                class="ml-4"
              >
                <v-icon>
                  {{
                    source.heartbeat === true
                      ? "mdi-web-check"
                      : source.heartbeat === false
                        ? "mdi-web-remove"
                        : source.disabled
                          ? "mdi-web-off"
                          : "mdi-web-refresh"
                  }}
                </v-icon>
              </v-avatar>
            </v-row>
          </v-card>
        </v-col>
      </v-row>
    </template>
  </RSection>
</template>
