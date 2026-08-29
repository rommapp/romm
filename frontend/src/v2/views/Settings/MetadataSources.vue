<script setup lang="ts">
// MetadataSources — v2-native rewrite. Provider tiles grouped by the
// shared provider taxonomy. Each tile shows:
//   • A circular logo
//   • Provider name + tone-coloured `RTag` status chip. Wording adapts
//     to how the provider is configured: key-based providers (IGDB,
//     ScreenScraper, MobyGames, RetroAchievements, SteamGridDB) talk
//     about the API key (missing / invalid / valid); flag-only
//     providers (LaunchBox, Flashpoint, HowLongToBeat, Hasheous,
//     PlayMatch) talk about the connection / enabled state.
//   • A "visit website" `RBtn`, plus a "get API key" `RBtn` shown only
//     for key-based providers (flag-only providers have no key to get).
//
// A warning banner sits above the tiles when the build carries no
// ScreenScraper developer credentials, since nothing on the tile itself
// can explain why a valid account still gets refused.
import { RAlert, RBtn, RTag } from "@v2/lib";
import { computed, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import storeConfig from "@/stores/config";
import storeHeartbeat from "@/stores/heartbeat";
import SettingsSection from "@/v2/components/Settings/SettingsSection.vue";
import {
  groupProviders,
  type MetadataProviderGroup,
  type MetadataProviderKey,
} from "@/v2/utils/metadataProviderGroups";

defineOptions({ inheritAttrs: false });

const { t } = useI18n();
const heartbeat = storeHeartbeat();
const configStore = storeConfig();

const heartbeatStatus = ref<Partial<Record<MetadataProviderKey, boolean>>>({});

type SourceStatus = "missing" | "invalid" | "ok" | "pending";

interface Source {
  name: string;
  /** Optional descriptor under the name — used by specialised sources
   *  (Achievements, Cover art, Completion times) so the user knows what
   *  each one contributes without having to recognise the brand. */
  subtitle?: string;
  key: MetadataProviderKey;
  logo: string;
  website: string;
  docsUrl: string;
  /** True when the provider is enabled by configuring an API key /
   *  credentials (so a "get API key" link is meaningful). False for
   *  free/public providers toggled by a plain `*_API_ENABLED` flag. */
  requiresKey: boolean;
  disabled: boolean;
  heartbeat?: boolean;
}

const sources = computed<Source[]>(() => [
  {
    name: "IGDB",
    key: "igdb",
    logo: "/assets/scrappers/igdb.png",
    website: "https://www.igdb.com",
    docsUrl: "https://api-docs.igdb.com/#account-creation",
    requiresKey: true,
    disabled: !heartbeat.value.METADATA_SOURCES?.IGDB_API_ENABLED,
    heartbeat: heartbeatStatus.value.igdb,
  },
  {
    name: "ScreenScraper",
    key: "ss",
    logo: "/assets/scrappers/ss.png",
    website: "https://www.screenscraper.fr",
    docsUrl: "https://www.screenscraper.fr/membreinscription.php",
    requiresKey: true,
    disabled: !heartbeat.value.METADATA_SOURCES?.SS_API_ENABLED,
    heartbeat: heartbeatStatus.value.ss,
  },
  {
    name: "MobyGames",
    key: "moby",
    logo: "/assets/scrappers/moby.png",
    website: "https://www.mobygames.com",
    docsUrl: "https://www.mobygames.com/info/api/",
    requiresKey: true,
    disabled: !heartbeat.value.METADATA_SOURCES?.MOBY_API_ENABLED,
    heartbeat: heartbeatStatus.value.moby,
  },
  {
    name: "LaunchBox",
    key: "launchbox",
    logo: "/assets/scrappers/launchbox.png",
    website: "https://www.launchbox-app.com",
    docsUrl: "https://gamesdb.launchbox-app.com",
    requiresKey: false,
    disabled: !heartbeat.value.METADATA_SOURCES?.LAUNCHBOX_API_ENABLED,
    heartbeat: heartbeatStatus.value.launchbox,
  },
  {
    name: "Flashpoint Archive",
    key: "flashpoint",
    logo: "/assets/scrappers/flashpoint.png",
    website: "https://flashpointarchive.org",
    docsUrl: "https://flashpointarchive.org/datahub/Flashpoint_API",
    requiresKey: false,
    disabled: !heartbeat.value.METADATA_SOURCES?.FLASHPOINT_API_ENABLED,
    heartbeat: heartbeatStatus.value.flashpoint,
  },
  {
    name: "RetroAchievements",
    subtitle: t("settings.metadata-subtitle-achievements"),
    key: "ra",
    logo: "/assets/scrappers/ra.png",
    website: "https://retroachievements.org",
    docsUrl: "https://retroachievements.org/APIDemo.php",
    requiresKey: true,
    disabled: !heartbeat.value.METADATA_SOURCES?.RA_API_ENABLED,
    heartbeat: heartbeatStatus.value.ra,
  },
  {
    name: "SteamGridDB",
    subtitle: t("settings.metadata-subtitle-cover-art"),
    key: "sgdb",
    logo: "/assets/scrappers/sgdb.png",
    website: "https://www.steamgriddb.com",
    docsUrl: "https://www.steamgriddb.com/profile/preferences/api",
    requiresKey: true,
    disabled: !heartbeat.value.METADATA_SOURCES?.STEAMGRIDDB_API_ENABLED,
    heartbeat: heartbeatStatus.value.sgdb,
  },
  {
    name: "HowLongToBeat",
    subtitle: t("settings.metadata-subtitle-completion"),
    key: "hltb",
    logo: "/assets/scrappers/hltb.png",
    website: "https://howlongtobeat.com",
    docsUrl: "https://howlongtobeat.com",
    requiresKey: false,
    disabled: !heartbeat.value.METADATA_SOURCES?.HLTB_API_ENABLED,
    heartbeat: heartbeatStatus.value.hltb,
  },
  {
    name: "Hasheous",
    key: "hasheous",
    logo: "/assets/scrappers/hasheous.png",
    website: "https://hasheous.org",
    docsUrl: "https://hasheous.org/index.html?page=apidocs",
    requiresKey: false,
    disabled: !heartbeat.value.METADATA_SOURCES?.HASHEOUS_API_ENABLED,
    heartbeat: heartbeatStatus.value.hasheous,
  },
  {
    name: "PlayMatch",
    key: "playmatch",
    logo: "/assets/scrappers/playmatch.png",
    website: "https://github.com/RetroRealm/playmatch",
    docsUrl: "https://github.com/RetroRealm/playmatch",
    requiresKey: false,
    disabled: !heartbeat.value.METADATA_SOURCES?.PLAYMATCH_API_ENABLED,
    heartbeat: heartbeatStatus.value.playmatch,
  },
]);

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

type RTagTone = "neutral" | "brand" | "success" | "danger" | "warning" | "info";
interface StatusInfo {
  tone: RTagTone;
  icon: string;
  label: string;
}

// Status chip wording depends on how the provider is configured.
// Key-based providers speak about the API key; flag-only providers
// speak about the enabled/connection state — "API key invalid" makes
// no sense for a provider that has no key.
function statusInfo(source: Source): StatusInfo {
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
        <article
          v-for="source in group.providers"
          :key="source.key"
          class="r-v2-meta__card"
          :data-provider="source.key"
          :class="{
            'r-v2-meta__card--missing': statusOf(source) === 'missing',
          }"
        >
          <header class="r-v2-meta__header">
            <div class="r-v2-meta__logo">
              <img :src="source.logo" :alt="source.name" />
            </div>
            <div class="r-v2-meta__head-text">
              <span class="r-v2-meta__name">{{ source.name }}</span>
              <span v-if="source.subtitle" class="r-v2-meta__subtitle">
                {{ source.subtitle }}
              </span>
              <RTag
                :tone="statusInfo(source).tone"
                :prepend-icon="statusInfo(source).icon"
                :text="statusInfo(source).label"
                size="x-small"
              />
            </div>
          </header>

          <div class="r-v2-meta__actions">
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
          </div>
        </article>
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

/* Card chrome — bg + 12px radius + overflow hidden so the inner
   border-top reaches the rounded corners cleanly. */
.r-v2-meta__card {
  border-radius: 12px;
  border: 1px solid var(--r-color-border);
  background: var(--r-color-surface);
  overflow: hidden;
  transition: border-color var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-v2-meta__card--missing {
  opacity: 0.7;
}

.r-v2-meta__header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px 16px 14px;
}

.r-v2-meta__logo {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  flex-shrink: 0;
  display: grid;
  place-items: center;
  background: var(--r-color-bg-elevated);
  border: 1px solid var(--r-color-border);
  padding: 6px;
}
.r-v2-meta__logo img {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
}

.r-v2-meta__head-text {
  min-width: 0;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 6px;
}

.r-v2-meta__name {
  font-size: 14px;
  font-weight: var(--r-font-weight-bold);
  color: var(--r-color-fg);
}

.r-v2-meta__subtitle {
  font-size: 11px;
  color: var(--r-color-fg-muted);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  font-weight: var(--r-font-weight-semibold);
}

.r-v2-meta__actions {
  display: flex;
  gap: 8px;
  padding: 12px 14px;
  border-top: 1px solid var(--r-color-border);
  background: var(--r-color-bg-elevated);
}
</style>
