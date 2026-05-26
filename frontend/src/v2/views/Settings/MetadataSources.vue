<script setup lang="ts">
// MetadataSources — v2-native rewrite. Provider tiles grouped into
// three categories (general catalogs, specialised sources, match
// proxies) matching the split used in the Setup wizard. Each tile
// shows:
//   • A circular logo
//   • Provider name + tone-coloured `RTag` status chip
//     (missing key / invalid key / connected / checking)
//   • Two `RBtn` action buttons (get API key — opens docs; visit
//     website) — both neutral, since the status chip carries the
//     state on its own.
import { RBtn, RTag } from "@v2/lib";
import { computed, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import storeConfig from "@/stores/config";
import storeHeartbeat from "@/stores/heartbeat";
import SettingsSection from "@/v2/components/Settings/SettingsSection.vue";

defineOptions({ inheritAttrs: false });

const { t } = useI18n();
const heartbeat = storeHeartbeat();
const configStore = storeConfig();

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
  playmatch: undefined,
});

type SourceStatus = "missing" | "invalid" | "ok" | "pending";

interface Source {
  name: string;
  /** Optional descriptor under the name — used by specialised sources
   *  (Achievements, Cover art, Completion times) so the user knows what
   *  each one contributes without having to recognise the brand. */
  subtitle?: string;
  value: string;
  logo: string;
  website: string;
  docsUrl: string;
  disabled: boolean;
  heartbeat?: boolean;
}

const catalogs = computed<Source[]>(() => [
  {
    name: "IGDB",
    value: "igdb",
    logo: "/assets/scrappers/igdb.png",
    website: "https://www.igdb.com",
    docsUrl: "https://api-docs.igdb.com/#account-creation",
    disabled: !heartbeat.value.METADATA_SOURCES?.IGDB_API_ENABLED,
    heartbeat: heartbeatStatus.value.igdb,
  },
  {
    name: "ScreenScraper",
    value: "ss",
    logo: "/assets/scrappers/ss.png",
    website: "https://www.screenscraper.fr",
    docsUrl: "https://www.screenscraper.fr/membreinscription.php",
    disabled: !heartbeat.value.METADATA_SOURCES?.SS_API_ENABLED,
    heartbeat: heartbeatStatus.value.ss,
  },
  {
    name: "MobyGames",
    value: "moby",
    logo: "/assets/scrappers/moby.png",
    website: "https://www.mobygames.com",
    docsUrl: "https://www.mobygames.com/info/api/",
    disabled: !heartbeat.value.METADATA_SOURCES?.MOBY_API_ENABLED,
    heartbeat: heartbeatStatus.value.moby,
  },
  {
    name: "LaunchBox",
    value: "launchbox",
    logo: "/assets/scrappers/launchbox.png",
    website: "https://www.launchbox-app.com",
    docsUrl: "https://gamesdb.launchbox-app.com",
    disabled: !heartbeat.value.METADATA_SOURCES?.LAUNCHBOX_API_ENABLED,
    heartbeat: heartbeatStatus.value.launchbox,
  },
  {
    name: "Flashpoint Archive",
    value: "flashpoint",
    logo: "/assets/scrappers/flashpoint.png",
    website: "https://flashpointarchive.org",
    docsUrl: "https://flashpointarchive.org/datahub/Flashpoint_API",
    disabled: !heartbeat.value.METADATA_SOURCES?.FLASHPOINT_API_ENABLED,
    heartbeat: heartbeatStatus.value.flashpoint,
  },
]);

const specialised = computed<Source[]>(() => [
  {
    name: "RetroAchievements",
    subtitle: t("settings.metadata-subtitle-achievements"),
    value: "ra",
    logo: "/assets/scrappers/ra.png",
    website: "https://retroachievements.org",
    docsUrl: "https://retroachievements.org/APIDemo.php",
    disabled: !heartbeat.value.METADATA_SOURCES?.RA_API_ENABLED,
    heartbeat: heartbeatStatus.value.ra,
  },
  {
    name: "SteamGridDB",
    subtitle: t("settings.metadata-subtitle-cover-art"),
    value: "sgdb",
    logo: "/assets/scrappers/sgdb.png",
    website: "https://www.steamgriddb.com",
    docsUrl: "https://www.steamgriddb.com/profile/preferences/api",
    disabled: !heartbeat.value.METADATA_SOURCES?.STEAMGRIDDB_API_ENABLED,
    heartbeat: heartbeatStatus.value.sgdb,
  },
  {
    name: "HowLongToBeat",
    subtitle: t("settings.metadata-subtitle-completion"),
    value: "hltb",
    logo: "/assets/scrappers/hltb.png",
    website: "https://howlongtobeat.com",
    docsUrl: "https://howlongtobeat.com",
    disabled: !heartbeat.value.METADATA_SOURCES?.HLTB_API_ENABLED,
    heartbeat: heartbeatStatus.value.hltb,
  },
]);

const proxies = computed<Source[]>(() => [
  {
    name: "Hasheous",
    value: "hasheous",
    logo: "/assets/scrappers/hasheous.png",
    website: "https://hasheous.org",
    docsUrl: "https://hasheous.org/index.html?page=apidocs",
    disabled: !heartbeat.value.METADATA_SOURCES?.HASHEOUS_API_ENABLED,
    heartbeat: heartbeatStatus.value.hasheous,
  },
  {
    name: "PlayMatch",
    value: "playmatch",
    logo: "/assets/scrappers/playmatch.png",
    website: "https://github.com/RetroRealm/playmatch",
    docsUrl: "https://github.com/RetroRealm/playmatch",
    disabled: !heartbeat.value.METADATA_SOURCES?.PLAYMATCH_API_ENABLED,
    heartbeat: heartbeatStatus.value.playmatch,
  },
]);

function statusOf(source: Source): SourceStatus {
  if (source.disabled) return "missing";
  if (source.heartbeat === true) return "ok";
  if (source.heartbeat === false) return "invalid";
  return "pending";
}

type RTagTone = "neutral" | "brand" | "success" | "danger" | "warning" | "info";
function statusTone(status: SourceStatus): RTagTone {
  if (status === "ok") return "success";
  if (status === "invalid") return "danger";
  if (status === "pending") return "warning";
  return "neutral";
}

function statusIcon(status: SourceStatus): string {
  if (status === "ok") return "mdi-check-circle-outline";
  if (status === "invalid") return "mdi-alert-circle-outline";
  if (status === "pending") return "mdi-progress-helper";
  return "mdi-key-alert-outline";
}

function statusLabel(status: SourceStatus): string {
  if (status === "ok") return t("scan.api-key-valid");
  if (status === "invalid") return t("scan.api-key-invalid");
  if (status === "pending") return t("scan.connection-in-progress");
  return t("scan.api-key-missing-short");
}

async function fetchAllHeartbeats() {
  const all = [...catalogs.value, ...specialised.value, ...proxies.value];
  await Promise.all(
    all
      .filter((source) => !source.disabled)
      .map(async (source) => {
        const result = await heartbeat.fetchMetadataHeartbeat(source.value);
        heartbeatStatus.value[source.value] = result;
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
    <SettingsSection
      :title="t('settings.metadata-catalogs')"
      icon="mdi-database-search-outline"
    >
      <div class="r-v2-meta__grid">
        <article
          v-for="source in catalogs"
          :key="source.value"
          class="r-v2-meta__card"
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
                :tone="statusTone(statusOf(source))"
                :icon="statusIcon(statusOf(source))"
                :text="statusLabel(statusOf(source))"
                size="x-small"
              />
            </div>
          </header>

          <div class="r-v2-meta__actions">
            <RBtn
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

    <SettingsSection
      :title="t('settings.metadata-specialised')"
      icon="mdi-puzzle-outline"
    >
      <div class="r-v2-meta__grid">
        <article
          v-for="source in specialised"
          :key="source.value"
          class="r-v2-meta__card"
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
                :tone="statusTone(statusOf(source))"
                :icon="statusIcon(statusOf(source))"
                :text="statusLabel(statusOf(source))"
                size="x-small"
              />
            </div>
          </header>

          <div class="r-v2-meta__actions">
            <RBtn
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

    <SettingsSection
      :title="t('settings.metadata-proxies')"
      icon="mdi-swap-horizontal-bold"
    >
      <div class="r-v2-meta__grid">
        <article
          v-for="source in proxies"
          :key="source.value"
          class="r-v2-meta__card"
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
                :tone="statusTone(statusOf(source))"
                :icon="statusIcon(statusOf(source))"
                :text="statusLabel(statusOf(source))"
                size="x-small"
              />
            </div>
          </header>

          <div class="r-v2-meta__actions">
            <RBtn
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
