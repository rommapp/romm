<script setup lang="ts">
// SiblingBadge — gallery overlay that exposes a ROM's grouped sibling
// versions. Visible only when `groupRoms` is on (the gallery is showing
// one card per sibling group); with grouping off every version is its
// own card and the chip would be redundant noise.
//
// Behaviour:
//   * Chip shows the total version count (this rom + its siblings).
//   * Hover or click opens a menu listing every version; each entry is
//     a router-link to that sibling's detail page. The current rom is
//     marked as the active row (radio-like) so the user can see which
//     one they're looking at.
//   * Click on the chip itself doesn't navigate — the rom's card
//     already handles its own click; the chip is a popover trigger only.
import { RIcon, RMenu, RMenuItem } from "@v2/lib";
import { computed, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useUISettings } from "@/composables/useUISettings";
import type { SimpleRom } from "@/stores/roms";

defineOptions({ inheritAttrs: false });

const props = defineProps<{
  rom: SimpleRom;
}>();

const { t } = useI18n();
const { groupRoms } = useUISettings();

// Menu-open state — exposed to the parent surface via the
// `.sibling-badge--pinned` class on the chip, so the GameCard can keep
// its hover chrome painted while the version list is open (same
// "pinned" pattern GameActionBtn uses for `more` / `status` menus).
const menuOpen = ref(false);

const visible = computed(
  () => groupRoms.value === true && props.rom.siblings.length > 0,
);

const totalCount = computed(() => props.rom.siblings.length + 1);

const tooltipText = computed(() =>
  t("rom.versions-count", { n: totalCount.value }),
);

// `[rom, ...siblings]` mirrors the order v1's VersionSwitcher uses. The
// current rom always leads so the user immediately reads "the one I'm
// looking at" before the alternates. `main` flags the user-marked
// default version — read off `rom_user` for this rom and off the
// per-sibling `is_main_sibling` field for the rest (the backend
// resolves it from the request user's RomUser).
const versions = computed(() => [
  {
    id: props.rom.id,
    label: props.rom.fs_name_no_ext,
    current: true,
    main: props.rom.rom_user?.is_main_sibling === true,
  },
  ...props.rom.siblings.map((s) => ({
    id: s.id,
    label: s.fs_name_no_ext,
    current: false,
    main: s.is_main_sibling === true,
  })),
]);

const mainTooltip = computed(() => t("rom.default-version"));

// Prevent the parent card's `router-link` from intercepting clicks on
// the chip / menu — without this the gallery would navigate to the
// current rom instead of opening the menu.
function stopCard(e: Event) {
  e.stopPropagation();
}
</script>

<template>
  <RMenu
    v-if="visible"
    v-model="menuOpen"
    location="bottom end"
    :offset="6"
    :open-on-hover="true"
  >
    <template #activator="{ props: activatorProps }">
      <button
        v-bind="activatorProps"
        type="button"
        class="sibling-badge"
        :class="{ 'sibling-badge--pinned': menuOpen }"
        :title="tooltipText"
        :aria-label="tooltipText"
        @click="stopCard"
        @mousedown="stopCard"
      >
        <RIcon icon="mdi-card-multiple-outline" size="13" />
        <span class="sibling-badge__count">{{ totalCount }}</span>
      </button>
    </template>

    <RMenuItem
      v-for="v in versions"
      :key="v.id"
      :to="`/rom/${v.id}`"
      :variant="v.current ? 'active' : 'default'"
      :icon="v.current ? 'mdi-check' : undefined"
      :label="v.label"
    >
      <template v-if="v.main" #append>
        <RIcon
          icon="mdi-bookmark-box"
          size="14"
          class="sibling-badge__main"
          :aria-label="mainTooltip"
        />
      </template>
    </RMenuItem>
  </RMenu>
</template>

<style scoped>
/* Vertical pill — same visual idiom as `GameActionBtn` with
   `orientation="vertical"` (icon stacked over the count) so the
   sibling badge reads as a sibling of the status badge in the
   right-side column. Positioning lives on the consuming surface
   (GameCard pins it via `:deep(.sibling-badge)`). */
.sibling-badge {
  appearance: none;
  display: inline-flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
  min-width: 28px;
  padding: 5px 4px;
  background: var(--r-color-overlay-scrim-soft);
  border: 1px solid var(--r-color-overlay-border);
  border-radius: var(--r-radius-pill);
  color: var(--r-color-overlay-fg);
  font-family: inherit;
  font-size: 10px;
  font-weight: var(--r-font-weight-semibold);
  line-height: 1;
  cursor: pointer;
  backdrop-filter: blur(6px);
  -webkit-backdrop-filter: blur(6px);
  transition:
    background var(--r-motion-fast) var(--r-motion-ease-out),
    border-color var(--r-motion-fast) var(--r-motion-ease-out),
    color var(--r-motion-fast) var(--r-motion-ease-out);
}
.sibling-badge:hover,
.sibling-badge--pinned {
  background: var(--r-color-overlay-scrim-strong);
  border-color: var(--r-color-overlay-border-strong);
}

.sibling-badge__count {
  display: inline-block;
  min-width: 1ch;
  text-align: center;
}

.sibling-badge__main {
  color: var(--r-color-brand-accent);
}
</style>
