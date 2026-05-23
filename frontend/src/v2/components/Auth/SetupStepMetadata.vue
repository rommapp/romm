<script setup lang="ts">
// SetupStepMetadata — Step 3 of the setup wizard. Informational only:
// shows which metadata sources are reachable right now (have a valid
// API key configured on the server) and which ones aren't. The user
// can't toggle them here — that's settings territory — but seeing the
// list before finishing the wizard sets expectations correctly.
import { RCard, RIcon, RImg } from "@v2/lib";
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import storeHeartbeat from "@/stores/heartbeat";

defineOptions({ inheritAttrs: false });

const { t } = useI18n();
const heartbeat = storeHeartbeat();

interface Source {
  name: string;
  logoPath: string;
  available: boolean;
}

const sources = computed<Source[]>(() => {
  const m = heartbeat.value.METADATA_SOURCES ?? {};
  return [
    {
      name: "IGDB",
      logoPath: "/assets/scrappers/igdb.png",
      available: !!m.IGDB_API_ENABLED,
    },
    {
      name: "MobyGames",
      logoPath: "/assets/scrappers/moby.png",
      available: !!m.MOBY_API_ENABLED,
    },
    {
      name: "ScreenScraper",
      logoPath: "/assets/scrappers/ss.png",
      available: !!m.SS_API_ENABLED,
    },
    {
      name: "RetroAchievements",
      logoPath: "/assets/scrappers/ra.png",
      available: !!m.RA_API_ENABLED,
    },
    {
      name: "Hasheous",
      logoPath: "/assets/scrappers/hasheous.png",
      available: !!m.HASHEOUS_API_ENABLED,
    },
    {
      name: "Launchbox",
      logoPath: "/assets/scrappers/launchbox.png",
      available: !!m.LAUNCHBOX_API_ENABLED,
    },
    {
      name: "Flashpoint Project",
      logoPath: "/assets/scrappers/flashpoint.png",
      available: !!m.FLASHPOINT_API_ENABLED,
    },
    {
      name: "HowLongToBeat",
      logoPath: "/assets/scrappers/hltb.png",
      available: !!m.HLTB_API_ENABLED,
    },
    {
      name: "SteamgridDB",
      logoPath: "/assets/scrappers/sgdb.png",
      available: !!m.STEAMGRIDDB_API_ENABLED,
    },
  ];
});

const available = computed(() => sources.value.filter((s) => s.available));
const disabled = computed(() => sources.value.filter((s) => !s.available));
</script>

<template>
  <section class="r-setup-metadata">
    <p class="r-setup-metadata__lead">
      {{ t("setup.metadata-sources-intro") }}
    </p>

    <div class="r-setup-metadata__columns">
      <div v-if="available.length > 0" class="r-setup-metadata__column">
        <h3 class="r-setup-metadata__column-title">
          <RIcon name="mdi-check-circle" color="success" :size="18" />
          <span>{{ t("setup.metadata-sources-available") }}</span>
          <span class="r-setup-metadata__column-count">
            {{ available.length }}
          </span>
        </h3>
        <ul class="r-setup-metadata__items">
          <li
            v-for="source in available"
            :key="source.name"
            class="r-setup-metadata__item"
            data-state="available"
          >
            <RImg
              :src="source.logoPath"
              :width="28"
              :height="28"
              class="r-setup-metadata__item-logo"
              :alt="source.name"
            />
            <span class="r-setup-metadata__item-name">{{ source.name }}</span>
            <RIcon name="mdi-check" color="success" :size="20" />
          </li>
        </ul>
      </div>

      <div v-if="disabled.length > 0" class="r-setup-metadata__column">
        <h3 class="r-setup-metadata__column-title">
          <RIcon name="mdi-key-alert-outline" color="warning" :size="18" />
          <span>{{ t("setup.metadata-sources-disabled") }}</span>
          <span class="r-setup-metadata__column-count">
            {{ disabled.length }}
          </span>
        </h3>
        <ul class="r-setup-metadata__items">
          <li
            v-for="source in disabled"
            :key="source.name"
            class="r-setup-metadata__item"
            data-state="disabled"
          >
            <RImg
              :src="source.logoPath"
              :width="28"
              :height="28"
              class="r-setup-metadata__item-logo"
              :alt="source.name"
            />
            <span class="r-setup-metadata__item-name">{{ source.name }}</span>
            <span class="r-setup-metadata__item-hint">
              {{ t("setup.metadata-missing-key") }}
            </span>
          </li>
        </ul>
      </div>
    </div>

    <RCard
      v-if="available.length === 0"
      class="r-setup-metadata__no-sources"
      variant="outlined"
      color="warning"
    >
      <RIcon name="mdi-information-outline" color="warning" :size="20" />
      <span>{{ t("setup.metadata-sources-intro") }}</span>
    </RCard>
  </section>
</template>

<style scoped>
.r-setup-metadata {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: var(--r-space-5);
}

.r-setup-metadata__lead {
  margin: 0;
  color: var(--r-color-fg-secondary);
  font-size: var(--r-font-size-md);
  line-height: var(--r-line-height-normal);
}

.r-setup-metadata__columns {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: var(--r-space-5);
}

.r-setup-metadata__column {
  display: flex;
  flex-direction: column;
  gap: var(--r-space-3);
}

.r-setup-metadata__column-title {
  display: flex;
  align-items: center;
  gap: var(--r-space-2);
  margin: 0;
  font-size: var(--r-font-size-sm);
  font-weight: var(--r-font-weight-semibold);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--r-color-fg-secondary);
}

.r-setup-metadata__column-count {
  margin-left: auto;
  font-size: var(--r-font-size-xs);
  color: var(--r-color-fg-muted);
  letter-spacing: normal;
  text-transform: none;
}

.r-setup-metadata__items {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--r-space-1);
}

.r-setup-metadata__item {
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  gap: var(--r-space-3);
  padding: var(--r-space-2) var(--r-space-3);
  border-radius: var(--r-radius-md);
  border: 1px solid var(--r-color-border);
  background: var(--r-color-surface);
}

.r-setup-metadata__item[data-state="available"] {
  border-color: color-mix(
    in srgb,
    var(--r-color-status-base-success) 25%,
    transparent
  );
  background: color-mix(
    in srgb,
    var(--r-color-status-base-success) 6%,
    transparent
  );
}

.r-setup-metadata__item-logo {
  border-radius: var(--r-radius-sm);
  background: var(--r-color-surface);
  padding: 2px;
}

.r-setup-metadata__item-name {
  color: var(--r-color-fg);
  font-size: var(--r-font-size-md);
  font-weight: var(--r-font-weight-medium);
}

.r-setup-metadata__item-hint {
  font-size: var(--r-font-size-xs);
  color: var(--r-color-fg-muted);
}

.r-setup-metadata__no-sources {
  display: flex;
  align-items: center;
  gap: var(--r-space-3);
  padding: var(--r-space-3) var(--r-space-4);
}
</style>
