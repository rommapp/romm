<script setup lang="ts">
// SettingsTab — platform-scoped settings rendered as the `Settings`
// tab inside Platform.vue. Surfaces the details table + cover-style
// picker. Same content as the previous `PlatformSettingsDrawer`, now
// rendered inline in the platform view.
//
// Mutation paths:
//   • `aspect_ratio` → `platformApi.updatePlatform({ platform: { …, aspect_ratio } })`
//     Optimistic: the picker updates `currentPlatform` immediately;
//     a snackbar fires on success/failure.
//
// Read-only data:
//   • Details table — same fields v1 exposed (name, slug, fs_slug,
//     category, generation, family, size). All sourced from the
//     `platform` prop so a backend sync re-renders automatically.
import { RChip, RIcon } from "@v2/lib";
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import platformApi from "@/services/api/platform";
import storePlatforms, { type Platform } from "@/stores/platforms";
import { formatBytes } from "@/utils";
import { useSnackbar } from "@/v2/composables/useSnackbar";
import storeGalleryRoms from "@/v2/stores/galleryRoms";

defineOptions({ inheritAttrs: false });

const props = defineProps<{
  platform: Platform;
}>();

const { t } = useI18n();
const snackbar = useSnackbar();
const platformsStore = storePlatforms();
const galleryRoms = storeGalleryRoms();

type DetailRow = { label: string; value: string };
const details = computed<DetailRow[]>(() => {
  const p = props.platform;
  const rows: DetailRow[] = [
    { label: t("common.name"), value: p.display_name },
    { label: t("common.slug"), value: p.slug },
    { label: t("settings.folder-name"), value: p.fs_slug },
  ];
  if (p.category)
    rows.push({ label: t("platform.category"), value: p.category });
  if (typeof p.generation === "number" && p.generation > 0) {
    rows.push({ label: t("platform.generation"), value: String(p.generation) });
  }
  if (p.family_name) {
    rows.push({ label: t("platform.family"), value: p.family_name });
  }
  if (typeof p.fs_size_bytes === "number") {
    rows.push({
      label: t("common.size-on-disk"),
      value: formatBytes(p.fs_size_bytes, 2),
    });
  }
  return rows;
});

// Aspect ratio — platform-specific options. DVD / Blu-ray / DS / PSP
// / Switch families each add their natural-fit aspect on top of the
// universal 2:3 / 3:4 / 1:1 / 16:11 baseline.
const DVD_PLATFORMS = new Set([
  "dvd-player",
  "ps2",
  "ngc",
  "wii",
  "wiiu",
  "xbox",
  "xbox360",
  "win",
]);
const BLU_RAY_PLATFORMS = new Set([
  "blu-ray-player",
  "ps3",
  "ps4",
  "ps5",
  "psvita",
  "xboxone",
  "series-x-s",
]);
const DS_3DS_PLATFORMS = new Set([
  "nds",
  "nintendo-dsi",
  "3ds",
  "new-nintendo-3ds",
  "psx",
  "dc",
]);
const PSP_PLATFORMS = new Set(["psp", "psp-minis"]);
const SWITCH_PLATFORMS = new Set(["switch", "switch-2"]);

interface AspectOption {
  name: string;
  size: number;
  source: string;
}

const aspectOptions = computed<AspectOption[]>(() => {
  const slug = props.platform.slug?.toLowerCase() ?? "";
  return [
    { name: "2 / 3", size: 2 / 3, source: "SteamGridDB" },
    { name: "3 / 4", size: 3 / 4, source: "IGDB / MobyGames" },
    {
      name: "1 / 1",
      size: 1 / 1,
      source: t("platform.old-squared-cases"),
    },
    {
      name: "16 / 11",
      size: 16 / 11,
      source: t("platform.old-horizontal-cases"),
    },
    ...(DVD_PLATFORMS.has(slug)
      ? [{ name: "0.71 / 1", size: 0.71 / 1, source: "DVD" }]
      : []),
    ...(BLU_RAY_PLATFORMS.has(slug)
      ? [
          {
            name: "0.79 / 1",
            size: 0.79 / 1,
            source: "Blu-ray (Full artwork)",
          },
          {
            name: "0.87 / 1",
            size: 0.87 / 1,
            source: "Blu-ray (Plastic header)",
          },
        ]
      : []),
    ...(DS_3DS_PLATFORMS.has(slug)
      ? [{ name: "1.08 / 1", size: 1.08 / 1, source: "Nintendo DS / 3DS" }]
      : []),
    ...(PSP_PLATFORMS.has(slug)
      ? [{ name: "0.58 / 1", size: 0.58 / 1, source: "PSP" }]
      : []),
    ...(SWITCH_PLATFORMS.has(slug)
      ? [{ name: "0.62 / 1", size: 0.62 / 1, source: "Switch" }]
      : []),
  ];
});

const selectedAspect = computed(() => props.platform.aspect_ratio ?? "3 / 4");

async function setAspect(option: AspectOption) {
  if (option.name === selectedAspect.value) return;
  try {
    const { data } = await platformApi.updatePlatform({
      platform: { ...props.platform, aspect_ratio: option.name },
    });
    platformsStore.update(data);
    if (galleryRoms.currentPlatform?.id === data.id) {
      galleryRoms.setCurrentPlatform(data);
    }
    snackbar.success(t("platform.updated") || "Platform updated", {
      icon: "mdi-check-bold",
    });
  } catch (err) {
    const e = err as {
      response?: { data?: { msg?: string } };
      message?: string;
    };
    snackbar.error(
      `Failed to update aspect ratio: ${
        e?.response?.data?.msg || e?.message || "unknown error"
      }`,
      { icon: "mdi-close-circle" },
    );
  }
}
</script>

<template>
  <div class="r-v2-plat-settings">
    <section class="r-v2-plat-settings__section">
      <header class="r-v2-plat-settings__section-head">
        <RIcon icon="mdi-information-outline" size="14" />
        <span>{{ t("common.details", "Details") }}</span>
      </header>
      <div class="r-v2-plat-settings__details">
        <div
          v-for="row in details"
          :key="row.label"
          class="r-v2-plat-settings__detail-row"
        >
          <span class="r-v2-plat-settings__detail-label">{{ row.label }}</span>
          <span class="r-v2-plat-settings__detail-value">{{ row.value }}</span>
        </div>
      </div>
    </section>

    <section class="r-v2-plat-settings__section">
      <header class="r-v2-plat-settings__section-head">
        <RIcon icon="mdi-aspect-ratio" size="14" />
        <span>{{ t("platform.cover-style") }}</span>
      </header>
      <div class="r-v2-plat-settings__aspects">
        <button
          v-for="opt in aspectOptions"
          :key="opt.name"
          type="button"
          class="r-v2-plat-settings__aspect"
          :class="{
            'r-v2-plat-settings__aspect--active': opt.name === selectedAspect,
          }"
          :aria-pressed="opt.name === selectedAspect"
          @click="setAspect(opt)"
        >
          <span
            class="r-v2-plat-settings__aspect-tile"
            :style="{ aspectRatio: String(opt.size) }"
          >
            <span class="r-v2-plat-settings__aspect-name">{{ opt.name }}</span>
          </span>
          <RChip
            size="x-small"
            variant="translucent"
            class="r-v2-plat-settings__aspect-source"
          >
            {{ opt.source }}
          </RChip>
        </button>
      </div>
    </section>
  </div>
</template>

<style scoped>
.r-v2-plat-settings {
  display: grid;
  /* Two-column layout — details on the left, cover-style picker on
     the right. Collapses to a single column on narrow viewports so
     the aspect grid keeps reasonable card sizing. */
  grid-template-columns: minmax(280px, 360px) 1fr;
  gap: 28px;
  align-items: start;
}

@media (max-width: 900px) {
  .r-v2-plat-settings {
    grid-template-columns: 1fr;
  }
}

.r-v2-plat-settings__section-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
  font-size: 11px;
  font-weight: var(--r-font-weight-bold);
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--r-color-fg-muted);
}

/* ── Details table ─────────────────────────────────────────────── */
.r-v2-plat-settings__details {
  display: flex;
  flex-direction: column;
  background: var(--r-color-bg-elevated);
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-md);
  overflow: hidden;
}
.r-v2-plat-settings__detail-row {
  display: grid;
  grid-template-columns: 140px 1fr;
  gap: 12px;
  padding: 10px 14px;
  font-size: 12px;
  border-bottom: 1px solid var(--r-color-border);
}
.r-v2-plat-settings__detail-row:last-child {
  border-bottom: 0;
}
.r-v2-plat-settings__detail-label {
  color: var(--r-color-fg-muted);
}
.r-v2-plat-settings__detail-value {
  color: var(--r-color-fg);
  word-break: break-all;
}

/* ── Aspect ratio grid ─────────────────────────────────────────── */
.r-v2-plat-settings__aspects {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 10px;
}
.r-v2-plat-settings__aspect {
  appearance: none;
  background: var(--r-color-bg-elevated);
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-md);
  padding: 10px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  color: var(--r-color-fg);
  transition:
    background var(--r-motion-fast) var(--r-motion-ease-out),
    border-color var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-v2-plat-settings__aspect:hover {
  background: var(--r-color-surface-hover);
  border-color: var(--r-color-border-strong);
}
.r-v2-plat-settings__aspect--active {
  background: color-mix(in srgb, var(--r-color-brand-primary) 14%, transparent);
  border-color: color-mix(
    in srgb,
    var(--r-color-brand-primary) 55%,
    transparent
  );
  color: var(--r-color-brand-primary);
}
.r-v2-plat-settings__aspect-tile {
  display: grid;
  place-items: center;
  width: 80%;
  background: var(--r-color-surface);
  border: 1px solid var(--r-color-border-strong);
  border-radius: 6px;
  font-size: 12px;
  font-weight: var(--r-font-weight-semibold);
  color: var(--r-color-fg-secondary);
}
.r-v2-plat-settings__aspect--active .r-v2-plat-settings__aspect-tile {
  border-color: color-mix(
    in srgb,
    var(--r-color-brand-primary) 60%,
    transparent
  );
  color: var(--r-color-brand-primary);
}
.r-v2-plat-settings__aspect-name {
  pointer-events: none;
}
.r-v2-plat-settings__aspect-source {
  font-size: 10px;
  text-align: center;
}
</style>
