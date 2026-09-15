<script setup lang="ts">
// MetadataSources: v2-native settings view. Provider tiles grouped by
// the shared provider taxonomy, rendered with the shared
// MetadataProviderCard (tile layout) from the shared provider registry.
// Each tile shows the logo, name + tone-coloured status chip, and a
// footer with a "visit website" button plus a "get API key" button for
// key-based providers.
//
// Status wording adapts to how the provider is configured: key-based
// providers (IGDB, ScreenScraper, MobyGames, RetroAchievements,
// SteamGridDB) talk about the API key (missing / invalid / valid);
// flag-only providers talk about the connection / enabled state.
//
// A warning banner sits above the tiles when the build carries no
// ScreenScraper developer credentials, since nothing on the tile itself
// can explain why a valid account still gets refused.
import { RAlert, RBtn } from "@v2/lib";
import { computed, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import storeConfig from "@/stores/config";
import storeHeartbeat from "@/stores/heartbeat";
import SettingsSection from "@/v2/components/Settings/SettingsSection.vue";
import MetadataProviderCard from "@/v2/components/shared/MetadataProviderCard/MetadataProviderCard.vue";
import type { ProviderCardStatus } from "@/v2/components/shared/MetadataProviderCard/types";
import {
  groupProviders,
  type MetadataProviderGroup,
  type MetadataProviderKey,
} from "@/v2/utils/metadataProviderGroups";
import {
  METADATA_PROVIDER_INFO,
  type MetadataProviderInfo,
} from "@/v2/utils/metadataProviderInfo";

defineOptions({ inheritAttrs: false });

const { t } = useI18n();
const heartbeat = storeHeartbeat();
const configStore = storeConfig();

const heartbeatStatus = ref<Partial<Record<MetadataProviderKey, boolean>>>({});

type SourceStatus = "missing" | "invalid" | "ok" | "pending";

interface Source extends MetadataProviderInfo {
  disabled: boolean;
  heartbeat?: boolean;
}

const sources = computed<Source[]>(() =>
  METADATA_PROVIDER_INFO.map((info) => ({
    ...info,
    disabled: !heartbeat.value.METADATA_SOURCES?.[info.enabledFlag],
    heartbeat: heartbeatStatus.value[info.key],
  })),
);

const GROUP_LABELS: Record<
  MetadataProviderGroup,
  { titleKey: string; icon: string }
> = {
  catalog: {
    titleKey: "settings.metadata-catalogs",
    icon: "mdi-database-search-outline",
  },
  specialised: {
    titleKey: "settings.metadata-specialised",
    icon: "mdi-puzzle-outline",
  },
  proxy: {
    titleKey: "settings.metadata-proxies",
    icon: "mdi-swap-horizontal-bold",
  },
};

const groups = computed(() => groupProviders(sources.value, GROUP_LABELS));

// Gated on a heartbeat having landed: the store defaults to "not set", and a
// backend that is down must not read as a ScreenScraper misconfiguration.
const missingSSDevCredentials = computed(
  () =>
    heartbeat.loaded &&
    !heartbeat.value.METADATA_SOURCES?.SS_DEV_CREDENTIALS_SET,
);

function statusOf(source: Source): SourceStatus {
  if (source.disabled) return "missing";
  if (source.heartbeat === true) return "ok";
  if (source.heartbeat === false) return "invalid";
  return "pending";
}

// Status chip wording depends on how the provider is configured.
// Key-based providers speak about the API key; flag-only providers
// speak about the enabled/connection state, since "API key invalid"
// makes no sense for a provider that has no key.
function statusInfo(source: Source): ProviderCardStatus {
  const status = statusOf(source);
  if (status === "ok") {
    return {
      tone: "success",
      icon: "mdi-check-circle-outline",
      label: source.requiresKey
        ? t("scan.api-key-valid")
        : t("scan.connection-successful"),
    };
  }
  if (status === "invalid") {
    return {
      tone: "danger",
      icon: "mdi-alert-circle-outline",
      label: source.requiresKey
        ? t("scan.api-key-invalid")
        : t("scan.connection-failed"),
    };
  }
  if (status === "pending") {
    return {
      tone: "warning",
      icon: "mdi-progress-helper",
      label: t("scan.connection-in-progress"),
    };
  }
  return {
    tone: "neutral",
    icon: source.requiresKey
      ? "mdi-key-alert-outline"
      : "mdi-power-plug-off-outline",
    label: source.requiresKey
      ? t("scan.api-key-missing-short")
      : t("scan.source-disabled"),
  };
}

async function fetchAllHeartbeats() {
  await Promise.all(
    sources.value
      .filter((source) => !source.disabled)
      .map(async (source) => {
        heartbeatStatus.value[source.key] =
          await heartbeat.fetchMetadataHeartbeat(source.key);
      }),
  );
}

onMounted(() => {
  configStore.fetchConfig();
  void fetchAllHeartbeats();
});
</script>

<template>
  <div class="r-v2-section-stack">
    <RAlert v-if="missingSSDevCredentials" type="warning">
      <template #title>
        {{ t("settings.metadata-ss-dev-credentials-title") }}
      </template>
      {{ t("settings.metadata-ss-dev-credentials-desc") }}
    </RAlert>

    <SettingsSection
      v-for="group in groups"
      :key="group.group"
      :title="t(group.titleKey)"
      :icon="group.icon"
    >
      <div class="r-v2-meta__grid" :data-group="group.group">
        <MetadataProviderCard
          v-for="source in group.providers"
          :key="source.key"
          :data-provider="source.key"
          :name="source.name"
          :logo="source.logo"
          :subtitle="source.subtitleKey ? t(source.subtitleKey) : undefined"
          :status="statusInfo(source)"
          :dimmed="statusOf(source) === 'missing'"
        >
          <template #actions>
            <RBtn
              v-if="source.requiresKey"
              variant="translucent"
              size="small"
              prepend-icon="mdi-key-variant"
              :href="source.docsUrl"
              target="_blank"
              rel="noopener noreferrer"
            >
              {{ t("settings.metadata-get-key") }}
            </RBtn>
            <RBtn
              variant="text"
              size="small"
              prepend-icon="mdi-open-in-new"
              :href="source.website"
              target="_blank"
              rel="noopener noreferrer"
            >
              {{ t("settings.metadata-website") }}
            </RBtn>
          </template>
        </MetadataProviderCard>
      </div>
    </SettingsSection>
  </div>
</template>

<style scoped>
/* 3-col grid; collapses gracefully on narrow viewports. The grid lives
   inside SettingsSection's body so we add padding here. */
.r-v2-meta__grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
  padding: 16px;
}
html[data-bp~="sm-and-down"] .r-v2-meta__grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}
html[data-bp~="xs"] .r-v2-meta__grid {
  grid-template-columns: minmax(0, 1fr);
}
</style>
