<script setup lang="ts">
// ScanPlatformRow — single ROM row inside a ScanPlatform body.
//
// Extracted so the same row markup can be rendered both inside a plain
// <ul> (small platforms) and inside an RVirtualScroller slot (large
// platforms, hundreds+ of ROMs streaming in during an initial scan).
// Provider chip logic and cover-fallback selection live here.
import { RImg, RTag } from "@v2/lib";
import { useI18n } from "vue-i18n";
import { ROUTES } from "@/plugins/router";
import type { SimpleRom } from "@/stores/roms";
import { getMissingCoverImage, getUnmatchedCoverImage } from "@/utils/covers";
import { useWebpSupport } from "@/v2/composables/useWebpSupport";

defineOptions({ inheritAttrs: false });

const props = defineProps<{
  rom: SimpleRom;
}>();

const { t } = useI18n();
const { toWebp } = useWebpSupport();

interface Provider {
  key: string;
  title: string;
  logo: string;
  bg?: string;
}
const PROVIDERS: readonly Provider[] = [
  { key: "hasheous_id", title: "Verified with Hasheous", logo: "hasheous.png" },
  { key: "igdb_id", title: "IGDB match", logo: "igdb.png" },
  { key: "ss_id", title: "ScreenScraper match", logo: "ss.png" },
  { key: "moby_id", title: "MobyGames match", logo: "moby.png" },
  {
    key: "launchbox_id",
    title: "LaunchBox match",
    logo: "launchbox.png",
    bg: "#185a7c",
  },
  { key: "ra_id", title: "RetroAchievements match", logo: "ra.png" },
  { key: "flashpoint_id", title: "Flashpoint match", logo: "flashpoint.png" },
  { key: "hltb_id", title: "HowLongToBeat match", logo: "hltb.png" },
  { key: "gamelist_id", title: "ES-DE match", logo: "esde.png" },
  { key: "libretro_id", title: "Libretro match", logo: "libretro.png" },
];

function activeProviders(rom: SimpleRom) {
  return PROVIDERS.filter((p) =>
    Boolean((rom as Record<string, unknown>)[p.key]),
  );
}

function coverFor(rom: SimpleRom): string {
  if (rom.path_cover_small) return toWebp(rom.path_cover_small);
  // Fallback procedural cover — distinct artwork for identified vs.
  // unmatched ROMs so a glance at the row tells you whether scanning
  // matched anything.
  return rom.is_identified
    ? getMissingCoverImage(rom.name || rom.fs_name)
    : getUnmatchedCoverImage(rom.name || rom.fs_name);
}
</script>

<template>
  <router-link
    :to="{ name: ROUTES.ROM, params: { rom: props.rom.id } }"
    class="r-v2-scan-platform__rom"
  >
    <RImg
      :src="coverFor(props.rom)"
      :alt="props.rom.name || props.rom.fs_name"
      :width="36"
      :height="48"
      cover
      class="r-v2-scan-platform__cover"
    />
    <div class="r-v2-scan-platform__rom-text">
      <div class="r-v2-scan-platform__rom-name">
        {{ props.rom.name || props.rom.fs_name }}
      </div>
      <div class="r-v2-scan-platform__rom-file">
        {{ props.rom.fs_name }}
      </div>
    </div>
    <div class="r-v2-scan-platform__rom-meta">
      <template v-if="props.rom.is_identifying">
        <RTag
          tone="warning"
          size="x-small"
          icon="mdi-search-web"
          :text="t('scan.identifying', 'Identifying…')"
        />
      </template>
      <template v-else>
        <RTag
          v-if="props.rom.is_unidentified"
          tone="danger"
          size="x-small"
          icon="mdi-close"
          :text="t('scan.not-identified')"
        />
        <span
          v-for="provider in activeProviders(props.rom)"
          :key="provider.key"
          class="r-v2-scan-platform__provider"
          :title="provider.title"
          :style="provider.bg ? { background: provider.bg } : undefined"
        >
          <img
            :src="`/assets/scrappers/${provider.logo}`"
            :alt="provider.title"
            width="16"
            height="16"
          />
        </span>
      </template>
    </div>
  </router-link>
</template>

<style scoped>
.r-v2-scan-platform__rom {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 16px;
  border-top: 1px solid var(--r-color-border);
  /* Fixed row height — required for RVirtualScroller's offset table to
     match what the row actually renders at. Padding + 48px cover +
     border = 65px. */
  box-sizing: border-box;
  height: 65px;
  /* The row is a router-link to the ROM detail page. Strip the default
     link chrome so it reads as a regular row, and give it a hover tint
     to signal it's a click target. */
  color: inherit;
  text-decoration: none;
  cursor: pointer;
  transition: background var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-v2-scan-platform__rom:hover,
.r-v2-scan-platform__rom:focus-visible {
  background: var(--r-color-surface-hover);
  outline: none;
}
.r-v2-scan-platform__cover {
  flex-shrink: 0;
  border-radius: var(--r-radius-sm);
  overflow: hidden;
}
.r-v2-scan-platform__rom-text {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.r-v2-scan-platform__rom-name {
  font-size: 14px;
  font-weight: var(--r-font-weight-medium);
  color: var(--r-color-fg);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.r-v2-scan-platform__rom-file {
  font-size: 11px;
  color: var(--r-color-fg-muted);
  font-family: var(--r-font-family-mono);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.r-v2-scan-platform__rom-meta {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}
.r-v2-scan-platform__provider {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border-radius: 4px;
  background: var(--r-color-surface);
  flex-shrink: 0;
}
.r-v2-scan-platform__provider img {
  display: block;
  object-fit: contain;
}
</style>
