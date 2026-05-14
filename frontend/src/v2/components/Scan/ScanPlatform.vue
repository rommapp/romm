<script setup lang="ts">
// ScanPlatform (v2) — one collapsible per scanning platform in the
// Scan view. Header shows the platform icon + name + per-platform
// chips (ROM count, firmware count, "not identified" badge). Body
// lists every newly-scanned ROM with a thumbnail, filename, and the
// per-provider match chips (IGDB, ScreenScraper, MobyGames, …) plus
// the in-flight "Identifying…" state.
//
// Feature composite (lives outside /lib) — knows about ScanningPlatform
// and SimpleRom shapes. Built from R primitives + small inline UI for
// the ROM thumbnail + provider chip grid.
import { RCollapsible, RImg, RPlatformIcon, RTag } from "@v2/lib";
import { useI18n } from "vue-i18n";
import type { SimpleRom } from "@/stores/roms";
import type { ScanningPlatform } from "@/stores/scanning";
import { getMissingCoverImage, getUnmatchedCoverImage } from "@/utils/covers";
import { useWebpSupport } from "@/v2/composables/useWebpSupport";

defineOptions({ inheritAttrs: false });

defineProps<{
  platform: ScanningPlatform;
  /** Controlled open state — v-model:open from Scan.vue. */
  open?: boolean;
}>();

defineEmits<{
  (e: "update:open", value: boolean): void;
}>();

const { t } = useI18n();
const { toWebp } = useWebpSupport();

// Provider chips that share the same shape (icon + tooltip). Order
// matches v1 so the visual rhythm is unchanged. `bg` is optional —
// providers with a brand-coloured tile (LaunchBox) override the
// default grey surface tone.
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
  <RCollapsible
    :model-value="open"
    @update:model-value="(v) => $emit('update:open', v)"
  >
    <template #header-prepend>
      <RPlatformIcon
        v-if="platform.slug"
        :key="platform.slug"
        :slug="platform.slug"
        :name="platform.display_name"
        :size="32"
      />
    </template>
    <template #title>
      {{ platform.display_name }}
    </template>
    <template #header-append>
      <RTag tone="brand" size="x-small" :text="String(platform.roms.length)" />
      <RTag
        v-if="platform.firmware_count > 0"
        tone="warning"
        size="x-small"
        icon="mdi-memory"
        :text="String(platform.firmware_count)"
        :title="t('scan.firmware-found', platform.firmware_count)"
      />
      <RTag
        v-if="!platform.is_identified"
        tone="danger"
        size="small"
        icon="mdi-close"
        :text="t('scan.not-identified').toUpperCase()"
      />
    </template>

    <ul class="r-v2-scan-platform__rom-list">
      <li
        v-for="rom in platform.roms"
        :key="rom.id"
        class="r-v2-scan-platform__rom"
      >
        <RImg
          :src="coverFor(rom)"
          :alt="rom.name || rom.fs_name"
          :width="36"
          :height="48"
          cover
          class="r-v2-scan-platform__cover"
        />
        <div class="r-v2-scan-platform__rom-text">
          <div class="r-v2-scan-platform__rom-name">
            {{ rom.name || rom.fs_name }}
          </div>
          <div class="r-v2-scan-platform__rom-file">
            {{ rom.fs_name }}
          </div>
        </div>
        <div class="r-v2-scan-platform__rom-meta">
          <template v-if="rom.is_identifying">
            <RTag
              tone="warning"
              size="x-small"
              icon="mdi-search-web"
              text="Identifying…"
            />
          </template>
          <template v-else>
            <RTag
              v-if="rom.is_unidentified"
              tone="danger"
              size="x-small"
              icon="mdi-close"
              :text="t('scan.not-identified')"
            />
            <span
              v-for="provider in activeProviders(rom)"
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
      </li>
      <li
        v-if="platform.roms.length === 0 && platform.firmware_count === 0"
        class="r-v2-scan-platform__empty"
      >
        {{ t("scan.no-new-roms") }}
      </li>
    </ul>
  </RCollapsible>
</template>

<style scoped>
/* Body — ROM list rows. */
.r-v2-scan-platform__rom-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
  background: var(--r-color-bg-elevated);
}
.r-v2-scan-platform__rom {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 16px;
  border-top: 1px solid var(--r-color-border);
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
.r-v2-scan-platform__empty {
  padding: 16px;
  text-align: center;
  color: var(--r-color-fg-muted);
  font-size: 13px;
}
</style>
