<script setup lang="ts">
// UserInterface — v2-native UI preferences view.
//
// Sections:
//   1. Language          (RSelect — prefix-label)
//   2. Theme             (3-button compact picker)
//   3. Home              (toggle grid)
//   4. Gallery           (toggle grid + boxart RSelect prefix-label)
//   5. Virtual collections (single toggle + RSelect prefix-label)
//   6. UI version        (v2-only, beta — kept last)
//
// The v1 "Platforms drawer" section was removed (no equivalent in v2).
// `useUISettings` still exposes `platformsGroupBy` for v1 — we just
// don't surface it here.
import { RIcon, RSelect, RTag } from "@v2/lib";
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import { useUISettings } from "@/composables/useUISettings";
import { useUiVersion } from "@/composables/useUiVersion";
import storeCollections from "@/stores/collections";
import SettingsSection from "@/v2/components/Settings/SettingsSection.vue";
import SettingsShell from "@/v2/components/Settings/SettingsShell.vue";
import SettingsToggleRow from "@/v2/components/Settings/SettingsToggleRow.vue";
import LanguageSelector from "@/v2/components/shared/LanguageSelector.vue";

const { t } = useI18n();
const uiVersion = useUiVersion();
const collectionsStore = storeCollections();

const {
  theme: selectedTheme,
  // Home
  showStats,
  showRecentRoms,
  showContinuePlaying,
  showPlatforms,
  showCollections,
  // Gallery
  groupRoms,
  showSiblings,
  showRegions,
  showLanguages,
  showStatus,
  showActionBar,
  showGameTitle,
  enable3DEffect,
  disableAnimations,
  enableExperimentalCache,
  boxartStyle,
  // Virtual collections
  showVirtualCollections,
  virtualCollectionType,
} = useUISettings();

type Theme = "dark" | "light" | "auto";
const themeOptions: { value: Theme; label: string; icon: string }[] = [
  {
    value: "dark",
    label: t("settings.theme-dark"),
    icon: "mdi-moon-waning-crescent",
  },
  {
    value: "light",
    label: t("settings.theme-light"),
    icon: "mdi-white-balance-sunny",
  },
  {
    value: "auto",
    label: t("settings.theme-auto"),
    icon: "mdi-theme-light-dark",
  },
];

function setTheme(value: Theme) {
  selectedTheme.value = value;
}

function setVersion(value: "v1" | "v2") {
  uiVersion.value = value;
}

const uiVersionCards = computed(() => [
  {
    value: "v1" as const,
    title: t("settings.ui-version-classic", "Classic UI"),
    icon: "mdi-star-outline",
    blurb: t(
      "settings.ui-version-classic-blurb",
      "The familiar RomM interface.",
    ),
    beta: false,
  },
  {
    value: "v2" as const,
    title: t("settings.ui-version-new", "New UI"),
    icon: "mdi-star-four-points",
    blurb: t(
      "settings.ui-version-new-blurb",
      "The new design language — switch is instant.",
    ),
    beta: true,
  },
]);

// Selects --------------------------------------------------------------
const boxartStyleItems = computed(() => [
  { title: t("settings.boxart-cover"), value: "cover_path" },
  { title: t("settings.boxart-box3d"), value: "box3d_path" },
  { title: t("settings.boxart-physical"), value: "physical_path" },
  { title: t("settings.boxart-miximage"), value: "miximage_path" },
]);

const virtualCollectionTypeItems = [
  { title: "IGDB Collection", value: "collection" },
  { title: "Franchise", value: "franchise" },
  { title: "Genre", value: "genre" },
  { title: "Play Mode", value: "mode" },
  { title: "Developer", value: "company" },
  { title: "All (slow)", value: "all" },
];

function onVirtualCollectionTypeChange(value: unknown) {
  const next = typeof value === "string" ? value : String(value ?? "");
  virtualCollectionType.value = next;
  collectionsStore.fetchVirtualCollections(next);
}
</script>

<template>
  <SettingsShell bare>
    <SettingsSection :title="t('settings.language')" icon="mdi-translate">
      <div class="r-v2-ui__field">
        <LanguageSelector prefix-label />
      </div>
    </SettingsSection>

    <SettingsSection :title="t('settings.theme')" icon="mdi-brush-variant">
      <div class="r-v2-ui__theme-row">
        <button
          v-for="opt in themeOptions"
          :key="opt.value"
          type="button"
          class="r-v2-ui__theme-btn"
          :class="{
            'r-v2-ui__theme-btn--active': selectedTheme === opt.value,
          }"
          :aria-pressed="selectedTheme === opt.value"
          @click="setTheme(opt.value)"
        >
          <RIcon :icon="opt.icon" size="14" />
          <span>{{ opt.label }}</span>
        </button>
      </div>
    </SettingsSection>

    <!-- Home: 5 toggles in a 2-col grid -->
    <SettingsSection :title="t('settings.home')" icon="mdi-home-outline">
      <div class="r-v2-ui__toggle-grid">
        <SettingsToggleRow
          v-model="showStats"
          :title="t('settings.show-stats')"
          :description="t('settings.show-stats-desc')"
        />
        <SettingsToggleRow
          v-model="showRecentRoms"
          :title="t('settings.show-recently-added')"
          :description="t('settings.show-recently-added-desc')"
        />
        <SettingsToggleRow
          v-model="showContinuePlaying"
          :title="t('settings.show-continue-playing')"
          :description="t('settings.show-continue-playing-desc')"
        />
        <SettingsToggleRow
          v-model="showPlatforms"
          :title="t('settings.show-platforms')"
          :description="t('settings.show-platforms-desc')"
        />
        <SettingsToggleRow
          v-model="showCollections"
          :title="t('settings.show-collections')"
          :description="t('settings.show-collections-desc')"
        />
      </div>
    </SettingsSection>

    <!-- Gallery: 10 toggles + boxart-style select -->
    <SettingsSection :title="t('settings.gallery')" icon="mdi-view-grid">
      <div class="r-v2-ui__toggle-grid">
        <SettingsToggleRow
          v-model="groupRoms"
          :title="t('settings.group-roms')"
          :description="t('settings.group-roms-desc')"
        />
        <SettingsToggleRow
          v-model="showSiblings"
          :title="t('settings.show-siblings')"
          :description="t('settings.show-siblings-desc')"
          :disabled="!groupRoms"
        />
        <SettingsToggleRow
          v-model="showGameTitle"
          :title="t('settings.show-game-titles')"
          :description="t('settings.show-game-titles-desc')"
        />
        <SettingsToggleRow
          v-model="showActionBar"
          :title="t('settings.show-actionbar')"
          :description="t('settings.show-actionbar-desc')"
        />
        <SettingsToggleRow
          v-model="showStatus"
          :title="t('settings.show-status')"
          :description="t('settings.show-status-desc')"
        />
        <SettingsToggleRow
          v-model="showRegions"
          :title="t('settings.show-regions')"
          :description="t('settings.show-regions-desc')"
        />
        <SettingsToggleRow
          v-model="showLanguages"
          :title="t('settings.show-languages')"
          :description="t('settings.show-languages-desc')"
        />
        <SettingsToggleRow
          v-model="enable3DEffect"
          :title="t('settings.enable-3d-effect')"
          :description="t('settings.enable-3d-effect-desc')"
        />
        <SettingsToggleRow
          v-model="disableAnimations"
          :title="t('settings.disable-animations')"
          :description="t('settings.disable-animations-desc')"
        />
        <SettingsToggleRow
          v-model="enableExperimentalCache"
          :title="t('settings.enable-experimental-cache')"
          :description="t('settings.enable-experimental-cache-desc')"
        />
      </div>
      <div class="r-v2-ui__field r-v2-ui__field--bordered">
        <RSelect
          v-model="boxartStyle"
          :items="boxartStyleItems"
          prefix-label="stacked"
          hide-details
        >
          <template #prefix-label>
            <RIcon icon="mdi-image-frame" size="14" />
            {{ t("settings.boxart-style") }}
          </template>
        </RSelect>
      </div>
    </SettingsSection>

    <!-- Virtual collections -->
    <SettingsSection
      :title="t('common.virtual-collections')"
      icon="mdi-bookmark-box-multiple"
    >
      <div class="r-v2-ui__toggle-grid r-v2-ui__toggle-grid--single">
        <SettingsToggleRow
          v-model="showVirtualCollections"
          :title="t('settings.show-virtual-collections')"
          :description="t('settings.show-virtual-collections-desc')"
        />
      </div>
      <div class="r-v2-ui__field r-v2-ui__field--bordered">
        <RSelect
          :model-value="virtualCollectionType"
          :items="virtualCollectionTypeItems"
          :disabled="!showVirtualCollections"
          prefix-label="stacked"
          hide-details
          @update:model-value="onVirtualCollectionTypeChange"
        >
          <template #prefix-label>
            <RIcon icon="mdi-shape-outline" size="14" />
            {{ t("settings.virtual-collection-type") }}
          </template>
        </RSelect>
      </div>
    </SettingsSection>

    <!-- UI version (v2-only, beta) — kept last for parity. -->
    <SettingsSection
      :title="t('settings.ui-version', 'UI version')"
      icon="mdi-new-box"
    >
      <div class="r-v2-ui__field">
        <p class="r-v2-ui__desc">
          {{
            t(
              "settings.ui-version-desc",
              "Preview the new RomM UI (beta). Switching is instant and you can flip back at any time.",
            )
          }}
        </p>
        <div class="r-v2-ui__version-grid">
          <button
            v-for="card in uiVersionCards"
            :key="card.value"
            type="button"
            class="r-v2-ui__version-card"
            :class="{
              'r-v2-ui__version-card--active': uiVersion === card.value,
            }"
            :aria-pressed="uiVersion === card.value"
            @click="setVersion(card.value)"
          >
            <span class="r-v2-ui__version-icon">
              <RIcon :icon="card.icon" size="22" />
            </span>
            <span class="r-v2-ui__version-body">
              <span class="r-v2-ui__version-titles">
                <span class="r-v2-ui__version-title">{{ card.title }}</span>
                <RTag
                  v-if="card.beta"
                  :label="t('common.beta', 'Beta')"
                  tone="warning"
                  size="x-small"
                />
              </span>
              <span class="r-v2-ui__version-blurb">{{ card.blurb }}</span>
            </span>
            <span v-if="uiVersion === card.value" class="r-v2-ui__version-dot">
              <RIcon icon="mdi-check" size="12" />
            </span>
          </button>
        </div>
      </div>
    </SettingsSection>
  </SettingsShell>
</template>

<style scoped>
/* Generic field row inside a section body. */
.r-v2-ui__field {
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.r-v2-ui__field--bordered {
  border-top: 1px solid var(--r-color-border);
}

.r-v2-ui__desc {
  margin: 0;
  color: var(--r-color-fg-muted);
  font-size: 13px;
  line-height: 1.5;
  max-width: 640px;
}

/* Toggle grid — 2 cols, hairline gap (the gap shows the section body's
   border colour through to give the divider effect). */
.r-v2-ui__toggle-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1px;
  background: var(--r-color-border);
}
.r-v2-ui__toggle-grid--single {
  grid-template-columns: 1fr;
}
html[data-bp~="xs"] .r-v2-ui__toggle-grid {
  grid-template-columns: 1fr;
}

/* Theme picker: 3 buttons in a flush row inside the section body. */
.r-v2-ui__theme-row {
  display: flex;
  gap: 10px;
  padding: 16px;
}
.r-v2-ui__theme-btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 10px;
  border-radius: 8px;
  border: 1px solid var(--r-color-border);
  background: var(--r-color-surface);
  color: var(--r-color-fg-muted);
  cursor: pointer;
  font-size: 13px;
  font-weight: var(--r-font-weight-medium);
  transition:
    background var(--r-motion-fast) var(--r-motion-ease-out),
    border-color var(--r-motion-fast) var(--r-motion-ease-out),
    color var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-v2-ui__theme-btn:hover {
  background: var(--r-color-surface-hover);
  color: var(--r-color-fg);
}
.r-v2-ui__theme-btn--active {
  border-color: color-mix(
    in srgb,
    var(--r-color-brand-primary) 60%,
    transparent
  );
  background: color-mix(in srgb, var(--r-color-brand-primary) 14%, transparent);
  color: var(--r-color-brand-primary);
}
html[data-bp~="xs"] .r-v2-ui__theme-row {
  flex-direction: column;
}

/* UI version cards (v2-only). */
.r-v2-ui__version-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.r-v2-ui__version-card {
  position: relative;
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 16px 18px;
  background: var(--r-color-surface);
  border: 1px solid var(--r-color-border);
  border-radius: 10px;
  color: var(--r-color-fg-secondary);
  cursor: pointer;
  text-align: left;
  transition:
    background var(--r-motion-fast) var(--r-motion-ease-out),
    border-color var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-v2-ui__version-card:hover {
  background: var(--r-color-surface-hover);
  border-color: var(--r-color-border-strong);
}
.r-v2-ui__version-card--active {
  background: color-mix(in srgb, var(--r-color-brand-primary) 12%, transparent);
  border-color: color-mix(
    in srgb,
    var(--r-color-brand-primary) 50%,
    transparent
  );
  color: var(--r-color-fg);
}

.r-v2-ui__version-icon {
  display: grid;
  place-items: center;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  flex-shrink: 0;
  background: color-mix(in srgb, var(--r-color-brand-primary) 14%, transparent);
  color: var(--r-color-brand-primary);
}

.r-v2-ui__version-body {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
  flex: 1;
}

.r-v2-ui__version-titles {
  display: flex;
  align-items: center;
  gap: 8px;
}
.r-v2-ui__version-title {
  font-size: 14px;
  font-weight: var(--r-font-weight-semibold);
  color: var(--r-color-fg);
}
.r-v2-ui__version-blurb {
  font-size: 12px;
  color: var(--r-color-fg-muted);
  line-height: 1.4;
}

.r-v2-ui__version-dot {
  position: absolute;
  top: 12px;
  right: 12px;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: var(--r-color-brand-primary);
  color: var(--r-color-overlay-emphasis-fg);
  display: grid;
  place-items: center;
  font-weight: var(--r-font-weight-bold);
}

html[data-bp~="xs"] .r-v2-ui__version-grid {
  grid-template-columns: 1fr;
}
</style>
