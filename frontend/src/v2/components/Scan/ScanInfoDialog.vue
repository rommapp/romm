<script setup lang="ts">
// ScanInfoDialog — reference card for the Scan view. Two tabs (same
// underlined-pill pattern as GameDetails): "Scan types" explains what
// each scan does in long form (matching v1's reference card); "Metadata
// providers" lists every provider RomM can talk to with one-line setup
// notes. Pure static content — it's a lookup card, not a configurator.
//
// Why static descriptions instead of i18n: the v1 `scan-types-info`
// key shipped as one HTML blob with `<strong>` + `<br>` — hard to
// translate by section and harder to restyle. Embedding the text as
// typed arrays here keeps the layout flexible. If i18n becomes
// necessary, each row maps cleanly to a key.
import { RAvatar, RDialog, RIcon, RTabNav } from "@v2/lib";
import { computed, ref } from "vue";
import { useI18n } from "vue-i18n";

defineProps<{
  modelValue: boolean;
}>();

defineEmits<{
  (e: "update:modelValue", value: boolean): void;
}>();

const { t } = useI18n();

type TabId = "types" | "providers";
const activeTab = ref<TabId>("types");

const tabs = computed(() => [
  {
    id: "types" as const,
    label: t("scan.scan-types", "Scan types"),
    icon: "mdi-magnify-scan",
  },
  {
    id: "providers" as const,
    label: t("scan.metadata-sources", "Metadata providers"),
    icon: "mdi-database-search",
  },
]);

const docsUrl = computed(() =>
  activeTab.value === "providers"
    ? "https://docs.romm.app/latest/Getting-Started/Metadata-Providers/"
    : "https://docs.romm.app/latest/Usage/LibraryManagement/#scan",
);

interface ScanTypeRow {
  id: string;
  title: string;
  // Long-form description — single paragraph or `\n\n`-separated. The
  // template splits on double-newline so each paragraph gets its own
  // `<p>` for spacing.
  desc: string;
}

const scanTypes = computed<ScanTypeRow[]>(() => [
  {
    id: "new_platforms",
    title: t("scan.new-platforms"),
    desc: "This will only look for platforms that are not already in RomM.",
  },
  {
    id: "quick",
    title: t("scan.quick-scan"),
    desc: "Scans for games that are not in the library yet (fastest).",
  },
  {
    id: "unmatched",
    title: t("scan.unmatched-games"),
    desc:
      "Attempts to match games that are not matched with the selected metadata sources.\n\n" +
      "For example, selecting IGDB and ScreenScraper will scan games that are not matched with IGDB or ScreenScraper.",
  },
  {
    id: "update",
    title: t("scan.update-metadata"),
    desc:
      "Updates the metadata for games that have been matched with selected metadata sources using the external ID (e.g. IGDB ID).\n\n" +
      "For example, selecting IGDB and ScreenScraper will update the metadata for games that are matched with IGDB or ScreenScraper, and will use igdb_id and/or ssfr_id to refetch the metadata from the respective providers.",
  },
  {
    id: "hashes",
    title: t("scan.hashes"),
    desc: "Recalculates hashes for all files in the selected platforms.",
  },
  {
    id: "complete",
    title: t("scan.complete-rescan"),
    desc:
      "Rescans and rematches all games in the selected platforms (slowest).\n\n" +
      "This will wipe all existing metadata matches, including the external IDs, and attempt to match them again, like on a fresh scan. Saves, states and notes will be preserved.",
  },
]);

interface ProviderRow {
  id: string;
  name: string;
  /** Logo path under /assets/scrappers/. Matches the same scheme the
   *  heartbeat store uses so consumers and reference share assets. */
  logo: string;
  /** Locale key for the description. Shared with the setup wizard's
   *  Step 3 so both views show the exact same text. */
  descKey: string;
  /** Locale key for the "how to configure" / env-var hint. */
  setupKey: string;
  /** Locale key for the optional warning / caveat pill. */
  caveatKey?: string;
}

const LOGO_BASE = "/assets/scrappers";

// Static reference set — every text string lives under the wizard's
// `setup.*` locale namespace so the Setup Wizard's Step 3 and this
// dialog never drift. Split into three groups, also mirroring the
// wizard:
//   * generalProviders   — full-record catalogs (IGDB, MobyGames, …)
//   * specificProviders  — single-dimension sources (achievements,
//                          cover art, completion times)
//   * proxies            — community hash matchers
const generalProviders: ProviderRow[] = [
  {
    id: "igdb",
    name: "IGDB",
    logo: `${LOGO_BASE}/igdb.png`,
    descKey: "setup.provider-igdb-desc",
    setupKey: "setup.provider-igdb-setup",
  },
  {
    id: "ss",
    name: "ScreenScraper",
    logo: `${LOGO_BASE}/ss.png`,
    descKey: "setup.provider-ss-desc",
    setupKey: "setup.provider-ss-setup",
  },
  {
    id: "moby",
    name: "MobyGames",
    logo: `${LOGO_BASE}/moby.png`,
    descKey: "setup.provider-moby-desc",
    setupKey: "setup.provider-moby-setup",
    caveatKey: "setup.provider-moby-caveat",
  },
  {
    id: "launchbox",
    name: "LaunchBox",
    logo: `${LOGO_BASE}/launchbox.png`,
    descKey: "setup.provider-launchbox-desc",
    setupKey: "setup.provider-launchbox-setup",
    caveatKey: "setup.provider-launchbox-caveat",
  },
  {
    id: "flashpoint",
    name: "Flashpoint",
    logo: `${LOGO_BASE}/flashpoint.png`,
    descKey: "setup.provider-flashpoint-desc",
    setupKey: "setup.provider-flashpoint-setup",
  },
];

const specificProviders: ProviderRow[] = [
  {
    id: "ra",
    name: "RetroAchievements",
    logo: `${LOGO_BASE}/ra.png`,
    descKey: "setup.provider-ra-desc",
    setupKey: "setup.provider-ra-setup",
    caveatKey: "setup.provider-ra-caveat",
  },
  {
    id: "sgdb",
    name: "SteamGridDB",
    logo: `${LOGO_BASE}/sgdb.png`,
    descKey: "setup.provider-sgdb-desc",
    setupKey: "setup.provider-sgdb-setup",
    caveatKey: "setup.provider-sgdb-caveat",
  },
  {
    id: "hltb",
    name: "How Long To Beat",
    logo: `${LOGO_BASE}/hltb.png`,
    descKey: "setup.provider-hltb-desc",
    setupKey: "setup.provider-hltb-setup",
    caveatKey: "setup.provider-hltb-caveat",
  },
];

const proxies: ProviderRow[] = [
  {
    id: "hasheous",
    name: "Hasheous",
    logo: `${LOGO_BASE}/hasheous.png`,
    descKey: "setup.proxy-hasheous-desc",
    setupKey: "setup.proxy-hasheous-setup",
    caveatKey: "setup.proxy-hasheous-caveat",
  },
  {
    id: "playmatch",
    name: "PlayMatch",
    logo: `${LOGO_BASE}/playmatch.png`,
    descKey: "setup.proxy-playmatch-desc",
    setupKey: "setup.proxy-playmatch-setup",
    caveatKey: "setup.proxy-playmatch-caveat",
  },
];

// Split a multi-line description on double-newline so each paragraph
// renders in its own `<p>`. Single newlines stay inline.
function paragraphs(text: string): string[] {
  return text
    .split("\n\n")
    .map((p) => p.trim())
    .filter(Boolean);
}
</script>

<template>
  <RDialog
    :model-value="modelValue"
    icon="mdi-information-outline"
    width="640px"
    height="640px"
    scroll-content
    @update:model-value="(v) => $emit('update:modelValue', v)"
  >
    <template #header>
      {{ t("scan.info-dialog-title", "Scan reference") }}
    </template>

    <template #toolbar>
      <RTabNav
        v-model="activeTab"
        :items="tabs"
        variant="underlined"
        size="small"
      />
    </template>

    <template #content>
      <div v-if="activeTab === 'types'" class="r-v2-scan-info__list">
        <article
          v-for="st in scanTypes"
          :key="st.id"
          class="r-v2-scan-info__row"
        >
          <h4 class="r-v2-scan-info__row-name">{{ st.title }}</h4>
          <div class="r-v2-scan-info__row-desc">
            <p
              v-for="(para, i) in paragraphs(st.desc)"
              :key="i"
              class="r-v2-scan-info__para"
            >
              {{ para }}
            </p>
          </div>
        </article>
      </div>

      <div v-else class="r-v2-scan-info__list">
        <!-- General providers — full-record catalogs. Section labels
             and per-provider strings come from the same `setup.*`
             locale keys the Setup Wizard's Step 3 uses, so the two
             views stay in sync. -->
        <section class="r-v2-scan-info__section">
          <header class="r-v2-scan-info__section-head">
            <span>{{ t("setup.metadata-catalogs") }}</span>
            <p class="r-v2-scan-info__section-hint">
              {{ t("setup.metadata-catalogs-hint") }}
            </p>
          </header>
          <article
            v-for="p in generalProviders"
            :key="p.id"
            class="r-v2-scan-info__row r-v2-scan-info__row--provider"
          >
            <div class="r-v2-scan-info__row-head">
              <RAvatar
                :image="p.logo"
                size="28"
                rounded="sm"
                class="r-v2-scan-info__logo"
              />
              <h4 class="r-v2-scan-info__row-name">{{ p.name }}</h4>
            </div>
            <div class="r-v2-scan-info__row-desc">
              <p class="r-v2-scan-info__para">{{ t(p.descKey) }}</p>
              <div class="r-v2-scan-info__meta">
                <span class="r-v2-scan-info__pill">
                  <RIcon icon="mdi-cog-outline" size="11" />
                  {{ t(p.setupKey) }}
                </span>
                <span
                  v-if="p.caveatKey"
                  class="r-v2-scan-info__pill r-v2-scan-info__pill--warn"
                >
                  <RIcon icon="mdi-alert-circle-outline" size="11" />
                  {{ t(p.caveatKey) }}
                </span>
              </div>
            </div>
          </article>
        </section>

        <!-- Specific providers — single-dimension sources. -->
        <section class="r-v2-scan-info__section">
          <header class="r-v2-scan-info__section-head">
            <span>{{ t("setup.metadata-specialised") }}</span>
            <p class="r-v2-scan-info__section-hint">
              {{ t("setup.metadata-specialised-hint") }}
            </p>
          </header>
          <article
            v-for="p in specificProviders"
            :key="p.id"
            class="r-v2-scan-info__row r-v2-scan-info__row--provider"
          >
            <div class="r-v2-scan-info__row-head">
              <RAvatar
                :image="p.logo"
                size="28"
                rounded="sm"
                class="r-v2-scan-info__logo"
              />
              <h4 class="r-v2-scan-info__row-name">{{ p.name }}</h4>
            </div>
            <div class="r-v2-scan-info__row-desc">
              <p class="r-v2-scan-info__para">{{ t(p.descKey) }}</p>
              <div class="r-v2-scan-info__meta">
                <span class="r-v2-scan-info__pill">
                  <RIcon icon="mdi-cog-outline" size="11" />
                  {{ t(p.setupKey) }}
                </span>
                <span
                  v-if="p.caveatKey"
                  class="r-v2-scan-info__pill r-v2-scan-info__pill--warn"
                >
                  <RIcon icon="mdi-alert-circle-outline" size="11" />
                  {{ t(p.caveatKey) }}
                </span>
              </div>
            </div>
          </article>
        </section>

        <!-- Proxies — community hash matchers. -->
        <section class="r-v2-scan-info__section">
          <header class="r-v2-scan-info__section-head">
            <span>{{ t("setup.metadata-proxies") }}</span>
            <p class="r-v2-scan-info__section-hint">
              {{ t("setup.metadata-proxies-hint") }}
            </p>
          </header>
          <article
            v-for="p in proxies"
            :key="p.id"
            class="r-v2-scan-info__row r-v2-scan-info__row--provider"
          >
            <div class="r-v2-scan-info__row-head">
              <RAvatar
                :image="p.logo"
                size="28"
                rounded="sm"
                class="r-v2-scan-info__logo"
              />
              <h4 class="r-v2-scan-info__row-name">{{ p.name }}</h4>
            </div>
            <div class="r-v2-scan-info__row-desc">
              <p class="r-v2-scan-info__para">{{ t(p.descKey) }}</p>
              <div class="r-v2-scan-info__meta">
                <span class="r-v2-scan-info__pill">
                  <RIcon icon="mdi-cog-outline" size="11" />
                  {{ t(p.setupKey) }}
                </span>
                <span
                  v-if="p.caveatKey"
                  class="r-v2-scan-info__pill r-v2-scan-info__pill--warn"
                >
                  <RIcon icon="mdi-alert-circle-outline" size="11" />
                  {{ t(p.caveatKey) }}
                </span>
              </div>
            </div>
          </article>
        </section>
      </div>
    </template>

    <template #footer>
      <a
        :href="docsUrl"
        target="_blank"
        rel="noopener"
        class="r-v2-scan-info__doc-link"
      >
        {{ t("scan.info-full-docs", "Read the full docs") }}
        <RIcon icon="mdi-open-in-new" size="12" />
      </a>
    </template>
  </RDialog>
</template>

<style scoped>
.r-v2-scan-info__list {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* Section grouping inside the providers tab — header + rows. The
   header is intentionally lightweight: small caps, muted icon, and an
   inline hint that explains the section in one sentence. */
.r-v2-scan-info__section {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.r-v2-scan-info__section-head {
  display: grid;
  grid-template-columns: auto 1fr;
  align-items: center;
  column-gap: 8px;
  row-gap: 2px;
  color: var(--r-color-fg-secondary);
}

.r-v2-scan-info__section-head > span {
  font-size: 11px;
  font-weight: var(--r-font-weight-semibold);
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.r-v2-scan-info__section-hint {
  grid-column: 1 / -1;
  margin: 0;
  font-size: 11.5px;
  color: var(--r-color-fg-muted);
}
.r-v2-scan-info__row {
  display: grid;
  grid-template-columns: 140px 1fr;
  gap: 14px;
  padding: 12px 14px;
  background: var(--r-color-bg-elevated);
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-md);
}
/* Provider row — the left column hosts logo + name as a vertical stack
   instead of just text, so the column width is the visual identity
   anchor for the row. */
.r-v2-scan-info__row--provider {
  align-items: start;
}
.r-v2-scan-info__row-head {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}
.r-v2-scan-info__logo {
  flex-shrink: 0;
  background: var(--r-color-surface);
}
.r-v2-scan-info__row-name {
  margin: 0;
  font-size: 13px;
  font-weight: var(--r-font-weight-semibold);
  color: var(--r-color-fg);
  align-self: flex-start;
  min-width: 0;
  /* Long names like "How Long To Beat" wrap inside the 140px column. */
  overflow-wrap: anywhere;
}
.r-v2-scan-info__row-desc {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.r-v2-scan-info__para {
  margin: 0;
  font-size: 12.5px;
  line-height: 1.55;
  color: var(--r-color-fg-secondary);
}

.r-v2-scan-info__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 2px;
}
/* Setup / caveat tags. `--r-radius-sm` to echo the parent card's
   `--r-radius-md` without doubling its curve — child corners read as
   "inside" the card instead of contrasting with it. */
.r-v2-scan-info__pill {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 8px;
  border-radius: var(--r-radius-sm);
  background: var(--r-color-surface);
  border: 1px solid var(--r-color-border);
  font-size: 11px;
  color: var(--r-color-fg-muted);
  font-family:
    var(--r-font-family-mono, ui-monospace), SFMono-Regular, monospace;
}
.r-v2-scan-info__pill--warn {
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

.r-v2-scan-info__doc-link {
  margin-left: auto;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: var(--r-font-weight-medium);
  color: var(--r-color-brand-primary);
  text-decoration: none;
  transition: color var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-v2-scan-info__doc-link:hover {
  color: var(--r-color-fg);
  text-decoration: underline;
}

/* Mobile — the 140px column for names gets tight at small widths.
   Stack name + desc vertically on narrow viewports. */
html[data-bp~="sm-and-down"] .r-v2-scan-info__row {
  grid-template-columns: 1fr;
  gap: 8px;
}
html[data-bp~="sm-and-down"] .r-v2-scan-info__row-head {
  /* Inline logo + name with a separator from the description below. */
  padding-bottom: 4px;
  border-bottom: 1px solid var(--r-color-border);
}
</style>
