<script setup lang="ts">
// GameHeader: right-column header for the details view.
// Four rows, top to bottom:
//   1. Title, or the game's scraped logo when the user opts in (+ previous /
//      next game arrows on the right, desktop only)
//   2. Meta (year · platform-icon + platform · verified RTag)
//   3. Tags (regions + languages + custom tags) as RTag primitives,
//      each a `searchLocation` pivot into the filtered search
//   4. GameActions (Play · Download · Favorite · Share · More)
//
// Metadata-provider links live in the Metadata tab, not the header.
// Genre/franchise belong in the Overview tab info grid.
import { RIcon, RTag, RTooltip } from "@v2/lib";
import { computed, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useUISettings } from "@/composables/useUISettings";
import type { DetailedRom } from "@/stores/roms";
import GameActions from "@/v2/components/GameActions/GameActions.vue";
import MainSiblingToggle from "@/v2/components/GameDetails/MainSiblingToggle.vue";
import PrevNextNav from "@/v2/components/GameDetails/PrevNextNav.vue";
import VersionSwitcher from "@/v2/components/GameDetails/VersionSwitcher.vue";
import PlatformIcon from "@/v2/components/shared/PlatformIcon.vue";
import { useBreakpoint } from "@/v2/composables/useBreakpoint";
import { useGameActions } from "@/v2/composables/useGameActions";
import { versionedResourceUrl } from "@/v2/utils/romFiles";
import { searchLocation } from "@/v2/utils/searchLocation";

defineOptions({ inheritAttrs: false });

const { t } = useI18n();
// Phones render the arrows around the cover instead (GameDetails).
const { smAndDown, xs } = useBreakpoint();

const props = defineProps<{
  rom: DetailedRom;
  title: string;
  platformLabel: string;
  releaseDate: string | null;
  verified: boolean;
  regions: string[];
  languages: string[];
  tags: string[];
}>();

const actions = useGameActions(() => props.rom);
const { showLogoTitle } = useUISettings();

const logoSrc = computed(() => {
  const path = props.rom.ss_metadata?.logo_path;
  return path ? versionedResourceUrl(path, props.rom.updated_at) : null;
});
// Load state is keyed on the URL, so a rescan that replaces the logo gets a
// fresh try.
const failedSrc = ref<string | null>(null);
const loadedLogo = ref<{ src: string; ratio: number } | null>(null);
const logoUrl = computed(() =>
  showLogoTitle.value && logoSrc.value !== failedSrc.value
    ? logoSrc.value
    : null,
);

// Logos are sized to a shared area rather than a shared height, so a square
// logo reads as large as a wide one.
const LOGO_MAX_WIDTH = 420;
const LOGO_BOX = {
  regular: { area: 40000, maxHeight: 176 },
  xs: { area: 22000, maxHeight: 120 },
};
const logoStyle = computed(() => {
  const box = xs.value ? LOGO_BOX.xs : LOGO_BOX.regular;
  const ratio =
    loadedLogo.value?.src === logoSrc.value ? loadedLogo.value.ratio : null;
  const width = ratio
    ? Math.min(Math.sqrt(box.area * ratio), box.maxHeight * ratio)
    : null;
  return {
    maxWidth: `min(100%, ${LOGO_MAX_WIDTH}px)`,
    maxHeight: `${box.maxHeight}px`,
    width: width ? `${Math.round(width)}px` : undefined,
  };
});
function onLogoLoad(event: Event) {
  const img = event.target as HTMLImageElement;
  if (logoSrc.value && img.naturalWidth && img.naturalHeight) {
    loadedLogo.value = {
      src: logoSrc.value,
      ratio: img.naturalWidth / img.naturalHeight,
    };
  }
}
</script>

<template>
  <div class="r-v2-det-header">
    <div class="r-v2-det-header__title-row">
      <h1
        class="r-v2-det-header__title"
        :class="{ 'r-v2-det-header__title--logo': logoUrl }"
      >
        <img
          v-if="logoUrl"
          :src="logoUrl"
          :alt="title"
          class="r-v2-det-header__logo"
          :style="logoStyle"
          @load="onLogoLoad"
          @error="failedSrc = logoSrc"
        />
        <template v-else>{{ title }}</template>
      </h1>
      <PrevNextNav v-if="!smAndDown" :rom-id="rom.id" />
    </div>

    <div class="r-v2-det-header__meta">
      <router-link
        v-if="actions.platformPath.value"
        :to="actions.platformPath.value"
        class="r-v2-det-header__platform"
        :aria-label="t('platform.browse-platform', { platform: platformLabel })"
      >
        <PlatformIcon
          :slug="rom.platform_slug"
          :fs-slug="rom.platform_fs_slug"
          :alt="platformLabel"
          :size="16"
        />
        {{ platformLabel }}
      </router-link>
      <span v-if="releaseDate" class="r-v2-det-header__sep"> · </span>
      <span v-if="releaseDate">{{ releaseDate }}</span>
      <span v-if="verified" class="r-v2-det-header__sep"> · </span>
      <!-- Icon-only verified indicator. The check decagram is a strong
           enough signal on its own; the "Verified" word was just noise
           in a row that's already mostly text. The tooltip spells out
           what "verified" means (a database hash match) so the badge
           isn't cryptic; the short label is the accessible name. -->
      <span
        v-if="verified"
        class="r-v2-det-header__verified"
        :aria-label="t('rom.verified-rom')"
        tabindex="0"
      >
        <RIcon icon="mdi-check-decagram" :size="18" color="success" />
        <RTooltip
          :text="t('rom.verified-rom-hint')"
          location="top"
          activator="parent"
        />
      </span>

      <span
        v-if="regions.length || languages.length || tags.length"
        class="r-v2-det-header__sep"
      >
        ·
      </span>

      <span
        v-if="regions.length || languages.length || tags.length"
        class="r-v2-det-header__tags"
      >
        <router-link
          v-for="r in regions"
          :key="`r-${r}`"
          :to="searchLocation('regions', r)"
          class="r-v2-det-header__tag-link"
        >
          <RTag :text="r" tone="info" size="small" />
        </router-link>
        <router-link
          v-for="l in languages"
          :key="`l-${l}`"
          :to="searchLocation('languages', l)"
          class="r-v2-det-header__tag-link"
        >
          <RTag :text="l" tone="brand" size="small" />
        </router-link>
        <router-link
          v-for="tag in tags"
          :key="`t-${tag}`"
          :to="searchLocation('tags', tag)"
          class="r-v2-det-header__tag-link"
        >
          <RTag :text="tag" size="small" />
        </router-link>
      </span>
    </div>

    <div v-if="rom.sibling_roms.length > 0" class="r-v2-det-header__versions">
      <VersionSwitcher :rom="rom" />
      <MainSiblingToggle :rom="rom" />
    </div>

    <GameActions :rom="rom" />
  </div>
</template>

<style scoped>
.r-v2-det-header {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding-top: 24px;
}

.r-v2-det-header__title-row {
  display: flex;
  align-items: flex-start;
  gap: 16px;
}

.r-v2-det-header__title {
  flex: 1;
  min-width: 0;
  font-size: var(--r-font-size-4xl);
  font-weight: var(--r-font-weight-extrabold);
  line-height: 1.1;
  letter-spacing: -0.02em;
  margin: 0 0 2px 0;
  color: var(--r-color-fg-heading);
  text-shadow: 0 2px 20px var(--r-color-title-shadow);
}

.r-v2-det-header__title--logo {
  display: flex;
}
/* A rim in the theme's text colour keeps dark lettering readable on dark,
   and light lettering on light. */
.r-v2-det-header__logo {
  --logo-rim: color-mix(in srgb, var(--r-color-fg) 50%, transparent);
  filter: drop-shadow(0 0 1px var(--logo-rim))
    drop-shadow(0 0 1px var(--logo-rim));
}

.r-v2-det-header__meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
  font-size: 13.5px;
  color: var(--r-color-fg-secondary);
}
.r-v2-det-header__sep {
  opacity: 0.3;
}
.r-v2-det-header__platform {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: inherit;
  text-decoration: none;
  cursor: pointer;
  border-radius: var(--r-radius-sm);
  transition: color 0.12s ease;
}
.r-v2-det-header__platform:hover {
  color: var(--r-color-fg);
}

.r-v2-det-header__verified {
  position: relative;
  display: inline-flex;
  align-items: center;
  line-height: 1;
}

.r-v2-det-header__tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.r-v2-det-header__tag-link {
  display: inline-flex;
  text-decoration: none;
  border-radius: var(--r-radius-chip);
}
/* Strengthen the border in the tag's own tone so the affordance reads the
   same for region / language / custom tags. */
.r-v2-det-header__tag-link:hover :deep(.r-tag) {
  --r-tag-border: var(--r-tag-fg);
}

.r-v2-det-header__versions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

html[data-bp~="xs"] .r-v2-det-header__title {
  font-size: 20px;
}

/* Mobile: the cover sits centred above this header, so centre the title and
   its meta / tag rows to match instead of the desktop left-align. */
html[data-bp~="sm-and-down"] .r-v2-det-header {
  align-items: center;
  text-align: center;
  padding-top: 4px;
}
html[data-bp~="sm-and-down"] .r-v2-det-header__title-row {
  align-self: stretch;
}
html[data-bp~="sm-and-down"] .r-v2-det-header__title--logo {
  justify-content: center;
}
html[data-bp~="sm-and-down"] .r-v2-det-header__meta,
html[data-bp~="sm-and-down"] .r-v2-det-header__tags,
html[data-bp~="sm-and-down"] .r-v2-det-header__versions {
  justify-content: center;
}
</style>
