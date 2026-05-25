<script setup lang="ts">
// SetupStepMetadata — Step 3 of the setup wizard. Informational only.
//
// Three sections, matching how Settings → Metadata sources groups them:
//   * General metadata — first-party catalogues (IGDB, MobyGames…)
//   * Specialised sources — achievements, cover art, completion times
//   * Match proxies — community hash matchers (Hasheous, Playmatch)
//
// For each source we surface two pieces of state separately:
//   * `disabled`  — admin flag from heartbeat (provider is enabled
//                   server-side, i.e. has any API key configured)
//   * `reachable` — runtime probe via /heartbeat/metadata: tells us
//                   whether the configured key actually works
// The combined status pill maps these to one of: disabled, missing /
// invalid key, checking, available.
import { RIcon, RImg, RTag } from "@v2/lib";
import { computed, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import storeHeartbeat from "@/stores/heartbeat";

defineOptions({ inheritAttrs: false });

const { t } = useI18n();
const heartbeat = storeHeartbeat();

type ProbeState = "pending" | "ok" | "ko";

interface Source {
  /** Key used both as the heartbeat probe identifier and as the
   *  status-map index. Matches what the existing settings view uses. */
  key: string;
  name: string;
  logoPath: string;
  descKey: string;
  /** Locale key for the env-var / config instructions. Shared with
   *  the Scan view's info dialog so both surfaces show the same
   *  setup hint per provider. */
  setupKey: string;
  /** Optional locale key for a warning / caveat pill. Shared too. */
  caveatKey?: string;
  disabled: boolean;
}

const probeStatus = ref<Record<string, ProbeState>>({});

const catalogs = computed<Source[]>(() => {
  const m = heartbeat.value.METADATA_SOURCES ?? {};
  return [
    {
      key: "igdb",
      name: "IGDB",
      logoPath: "/assets/scrappers/igdb.png",
      descKey: "setup.provider-igdb-desc",
      setupKey: "setup.provider-igdb-setup",
      disabled: !m.IGDB_API_ENABLED,
    },
    {
      key: "ss",
      name: "ScreenScraper",
      logoPath: "/assets/scrappers/ss.png",
      descKey: "setup.provider-ss-desc",
      setupKey: "setup.provider-ss-setup",
      disabled: !m.SS_API_ENABLED,
    },
    {
      key: "moby",
      name: "MobyGames",
      logoPath: "/assets/scrappers/moby.png",
      descKey: "setup.provider-moby-desc",
      setupKey: "setup.provider-moby-setup",
      caveatKey: "setup.provider-moby-caveat",
      disabled: !m.MOBY_API_ENABLED,
    },
    {
      key: "launchbox",
      name: "LaunchBox",
      logoPath: "/assets/scrappers/launchbox.png",
      descKey: "setup.provider-launchbox-desc",
      setupKey: "setup.provider-launchbox-setup",
      caveatKey: "setup.provider-launchbox-caveat",
      disabled: !m.LAUNCHBOX_API_ENABLED,
    },
    {
      key: "flashpoint",
      name: "Flashpoint",
      logoPath: "/assets/scrappers/flashpoint.png",
      descKey: "setup.provider-flashpoint-desc",
      setupKey: "setup.provider-flashpoint-setup",
      disabled: !m.FLASHPOINT_API_ENABLED,
    },
  ];
});

const specialised = computed<Source[]>(() => {
  const m = heartbeat.value.METADATA_SOURCES ?? {};
  return [
    {
      key: "ra",
      name: "RetroAchievements",
      logoPath: "/assets/scrappers/ra.png",
      descKey: "setup.provider-ra-desc",
      setupKey: "setup.provider-ra-setup",
      caveatKey: "setup.provider-ra-caveat",
      disabled: !m.RA_API_ENABLED,
    },
    {
      key: "sgdb",
      name: "SteamGridDB",
      logoPath: "/assets/scrappers/sgdb.png",
      descKey: "setup.provider-sgdb-desc",
      setupKey: "setup.provider-sgdb-setup",
      caveatKey: "setup.provider-sgdb-caveat",
      disabled: !m.STEAMGRIDDB_API_ENABLED,
    },
    {
      key: "hltb",
      name: "HowLongToBeat",
      logoPath: "/assets/scrappers/hltb.png",
      descKey: "setup.provider-hltb-desc",
      setupKey: "setup.provider-hltb-setup",
      caveatKey: "setup.provider-hltb-caveat",
      disabled: !m.HLTB_API_ENABLED,
    },
  ];
});

const proxies = computed<Source[]>(() => {
  const m = heartbeat.value.METADATA_SOURCES ?? {};
  return [
    {
      key: "hasheous",
      name: "Hasheous",
      logoPath: "/assets/scrappers/hasheous.png",
      descKey: "setup.proxy-hasheous-desc",
      setupKey: "setup.proxy-hasheous-setup",
      caveatKey: "setup.proxy-hasheous-caveat",
      disabled: !m.HASHEOUS_API_ENABLED,
    },
    {
      key: "playmatch",
      name: "PlayMatch",
      logoPath: "/assets/scrappers/playmatch.png",
      descKey: "setup.proxy-playmatch-desc",
      setupKey: "setup.proxy-playmatch-setup",
      caveatKey: "setup.proxy-playmatch-caveat",
      disabled: !m.PLAYMATCH_API_ENABLED,
    },
  ];
});

type StatusTone = "neutral" | "success" | "warning" | "danger";
interface StatusInfo {
  label: string;
  icon: string;
  tone: StatusTone;
}

function statusOf(source: Source): StatusInfo {
  if (source.disabled) {
    return {
      label: t("setup.metadata-status-key-missing"),
      icon: "mdi-key-alert-outline",
      tone: "warning",
    };
  }
  const probe = probeStatus.value[source.key] ?? "pending";
  if (probe === "ok") {
    return {
      label: t("setup.metadata-status-available"),
      icon: "mdi-check-circle-outline",
      tone: "success",
    };
  }
  if (probe === "ko") {
    return {
      label: t("setup.metadata-status-key-invalid"),
      icon: "mdi-alert-circle-outline",
      tone: "danger",
    };
  }
  return {
    label: t("setup.metadata-status-checking"),
    icon: "mdi-progress-helper",
    tone: "neutral",
  };
}

function itemDataState(source: Source): "available" | "checking" | "missing" {
  if (source.disabled) return "missing";
  const probe = probeStatus.value[source.key];
  if (probe === "ok") return "available";
  return "checking";
}

async function probeAll() {
  const all = [...catalogs.value, ...specialised.value, ...proxies.value];
  await Promise.all(
    all
      .filter((source) => !source.disabled)
      .map(async (source) => {
        probeStatus.value[source.key] = "pending";
        const ok = await heartbeat.fetchMetadataHeartbeat(source.key);
        probeStatus.value[source.key] = ok ? "ok" : "ko";
      }),
  );
}

onMounted(() => {
  void probeAll();
});
</script>

<template>
  <section class="r-setup-metadata">
    <p class="r-setup-metadata__lead">
      {{ t("setup.metadata-sources-intro") }}
    </p>

    <div class="r-setup-metadata__scroll">
      <!-- General metadata -->
      <div class="r-setup-metadata__group">
        <header class="r-setup-metadata__group-head">
          <div class="r-setup-metadata__group-title">
            <span>{{ t("setup.metadata-catalogs") }}</span>
          </div>
          <p class="r-setup-metadata__group-hint">
            {{ t("setup.metadata-catalogs-hint") }}
          </p>
        </header>

        <ul class="r-setup-metadata__items">
          <li
            v-for="source in catalogs"
            :key="source.key"
            class="r-setup-metadata__item"
            :data-state="itemDataState(source)"
          >
            <RImg
              :src="source.logoPath"
              :width="36"
              :height="36"
              class="r-setup-metadata__item-logo"
              :alt="source.name"
            />
            <div class="r-setup-metadata__item-body">
              <span class="r-setup-metadata__item-name">{{ source.name }}</span>
              <span class="r-setup-metadata__item-desc">
                {{ t(source.descKey) }}
              </span>
              <div class="r-setup-metadata__item-meta">
                <span class="r-setup-metadata__pill">
                  <RIcon icon="mdi-cog-outline" size="11" />
                  {{ t(source.setupKey) }}
                </span>
                <span
                  v-if="source.caveatKey"
                  class="r-setup-metadata__pill r-setup-metadata__pill--warn"
                >
                  <RIcon icon="mdi-alert-circle-outline" size="11" />
                  {{ t(source.caveatKey) }}
                </span>
              </div>
            </div>
            <RTag
              size="small"
              :tone="statusOf(source).tone"
              :prepend-icon="statusOf(source).icon"
            >
              {{ statusOf(source).label }}
            </RTag>
          </li>
        </ul>
      </div>

      <!-- Specialised sources -->
      <div class="r-setup-metadata__group">
        <header class="r-setup-metadata__group-head">
          <div class="r-setup-metadata__group-title">
            <span>{{ t("setup.metadata-specialised") }}</span>
          </div>
          <p class="r-setup-metadata__group-hint">
            {{ t("setup.metadata-specialised-hint") }}
          </p>
        </header>

        <ul class="r-setup-metadata__items">
          <li
            v-for="source in specialised"
            :key="source.key"
            class="r-setup-metadata__item"
            :data-state="itemDataState(source)"
          >
            <RImg
              :src="source.logoPath"
              :width="36"
              :height="36"
              class="r-setup-metadata__item-logo"
              :alt="source.name"
            />
            <div class="r-setup-metadata__item-body">
              <span class="r-setup-metadata__item-name">{{ source.name }}</span>
              <span class="r-setup-metadata__item-desc">
                {{ t(source.descKey) }}
              </span>
              <div class="r-setup-metadata__item-meta">
                <span class="r-setup-metadata__pill">
                  <RIcon icon="mdi-cog-outline" size="11" />
                  {{ t(source.setupKey) }}
                </span>
                <span
                  v-if="source.caveatKey"
                  class="r-setup-metadata__pill r-setup-metadata__pill--warn"
                >
                  <RIcon icon="mdi-alert-circle-outline" size="11" />
                  {{ t(source.caveatKey) }}
                </span>
              </div>
            </div>
            <RTag
              size="small"
              :tone="statusOf(source).tone"
              :prepend-icon="statusOf(source).icon"
            >
              {{ statusOf(source).label }}
            </RTag>
          </li>
        </ul>
      </div>

      <!-- Match proxies -->
      <div class="r-setup-metadata__group">
        <header class="r-setup-metadata__group-head">
          <div class="r-setup-metadata__group-title">
            <span>{{ t("setup.metadata-proxies") }}</span>
          </div>
          <p class="r-setup-metadata__group-hint">
            {{ t("setup.metadata-proxies-hint") }}
          </p>
        </header>

        <ul class="r-setup-metadata__items">
          <li
            v-for="source in proxies"
            :key="source.key"
            class="r-setup-metadata__item"
            :data-state="itemDataState(source)"
          >
            <RImg
              :src="source.logoPath"
              :width="36"
              :height="36"
              class="r-setup-metadata__item-logo"
              :alt="source.name"
            />
            <div class="r-setup-metadata__item-body">
              <span class="r-setup-metadata__item-name">{{ source.name }}</span>
              <span class="r-setup-metadata__item-desc">
                {{ t(source.descKey) }}
              </span>
              <div class="r-setup-metadata__item-meta">
                <span class="r-setup-metadata__pill">
                  <RIcon icon="mdi-cog-outline" size="11" />
                  {{ t(source.setupKey) }}
                </span>
                <span
                  v-if="source.caveatKey"
                  class="r-setup-metadata__pill r-setup-metadata__pill--warn"
                >
                  <RIcon icon="mdi-alert-circle-outline" size="11" />
                  {{ t(source.caveatKey) }}
                </span>
              </div>
            </div>
            <RTag
              size="small"
              :tone="statusOf(source).tone"
              :prepend-icon="statusOf(source).icon"
            >
              {{ statusOf(source).label }}
            </RTag>
          </li>
        </ul>
      </div>
    </div>
  </section>
</template>

<style scoped>
.r-setup-metadata {
  flex: 1 1 auto;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: var(--r-space-4);
}

.r-setup-metadata__lead {
  margin: 0 auto;
  max-width: 900px;
  text-align: center;
  color: var(--r-color-fg-secondary);
  font-size: var(--r-font-size-md);
  line-height: var(--r-line-height-normal);
}

.r-setup-metadata__scroll {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: var(--r-space-5);
  padding-right: var(--r-space-1);
}

/* ── Group chrome ────────────────────────────────────────────────── */
.r-setup-metadata__group {
  display: flex;
  flex-direction: column;
  gap: var(--r-space-3);
}

.r-setup-metadata__group-head {
  display: flex;
  flex-direction: column;
  gap: var(--r-space-1);
}

.r-setup-metadata__group-title {
  display: flex;
  align-items: center;
  gap: var(--r-space-2);
  font-size: var(--r-font-size-sm);
  font-weight: var(--r-font-weight-semibold);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--r-color-fg-secondary);
}

.r-setup-metadata__group-hint {
  margin: 0;
  font-size: var(--r-font-size-xs);
  color: var(--r-color-fg-muted);
}

/* ── Items ───────────────────────────────────────────────────────── */
.r-setup-metadata__items {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(360px, 1fr));
  gap: var(--r-space-2);
}

.r-setup-metadata__item {
  display: grid;
  grid-template-columns: 36px minmax(0, 1fr) auto;
  align-items: center;
  gap: var(--r-space-3);
  padding: var(--r-space-3) var(--r-space-4);
  border-radius: var(--r-radius-md);
  background: var(--r-color-surface);
  border: 1px solid var(--r-color-border);
  transition:
    background 200ms ease,
    border-color 200ms ease;
}

.r-setup-metadata__item[data-state="available"] {
  border-color: color-mix(
    in srgb,
    var(--r-color-status-base-success) 30%,
    transparent
  );
  background: color-mix(
    in srgb,
    var(--r-color-status-base-success) 6%,
    transparent
  );
}

.r-setup-metadata__item[data-state="missing"] {
  opacity: 0.75;
}

.r-setup-metadata__item-logo {
  border-radius: var(--r-radius-sm);
  background: var(--r-color-surface);
  padding: 2px;
}

.r-setup-metadata__item-body {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.r-setup-metadata__item-name {
  font-size: var(--r-font-size-md);
  font-weight: var(--r-font-weight-semibold);
  color: var(--r-color-fg);
}

.r-setup-metadata__item-desc {
  font-size: var(--r-font-size-xs);
  color: var(--r-color-fg-muted);
  line-height: var(--r-line-height-normal);
}

/* Setup / caveat pills — same vocabulary as the Scan view's info
   dialog (the source-of-truth locale keys live in `setup.*`, used
   by both surfaces). Wrap so dense env-var instructions can flow
   onto a second line on narrow viewports. */
.r-setup-metadata__item-meta {
  display: flex;
  flex-wrap: wrap;
  gap: var(--r-space-1);
  margin-top: var(--r-space-1);
}
.r-setup-metadata__pill {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 8px;
  border-radius: var(--r-radius-sm);
  background: var(--r-color-surface);
  border: 1px solid var(--r-color-border);
  font-size: var(--r-font-size-xs);
  color: var(--r-color-fg-muted);
  font-family:
    var(--r-font-family-mono, ui-monospace), SFMono-Regular, monospace;
}
.r-setup-metadata__pill--warn {
  background: color-mix(
    in srgb,
    var(--r-color-status-base-warning) 14%,
    transparent
  );
  border-color: color-mix(
    in srgb,
    var(--r-color-status-base-warning) 36%,
    transparent
  );
  color: var(--r-color-warning);
  font-family: inherit;
}
</style>
