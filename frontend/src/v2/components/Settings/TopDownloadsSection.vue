<script setup lang="ts">
// TopDownloadsSection, most-downloaded games, ranked. Rows link
// through to the game page so an admin can act on what they see.
import { RIcon, RTable, type RTableColumn } from "@v2/lib";
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import { useRouter } from "vue-router";
import type { TopDownloadedRom } from "@/__generated__";
import { ROUTES } from "@/plugins/router";
import { formatBytes, formatTimestamp } from "@/utils";
import SettingsSection from "@/v2/components/Settings/SettingsSection.vue";

defineOptions({ inheritAttrs: false });

interface Props {
  roms: readonly TopDownloadedRom[];
  loading?: boolean;
}
const props = defineProps<Props>();

const { t, locale } = useI18n();
const router = useRouter();

const columns = computed<RTableColumn[]>(() => [
  { key: "rank", label: "#", width: "44px", skeletonWidth: 16 },
  {
    key: "rom_name",
    label: t("common.name"),
    width: "minmax(0, 2fr)",
    skeletonWidth: 180,
  },
  {
    key: "platform_name",
    label: t("common.platform"),
    width: "minmax(0, 1fr)",
    skeletonWidth: 100,
  },
  {
    key: "download_count",
    label: t("settings.downloads-column-count"),
    width: "110px",
    align: "end",
    skeletonWidth: 40,
  },
  {
    key: "file_size_bytes",
    label: t("common.size-on-disk"),
    width: "110px",
    align: "end",
    skeletonWidth: 60,
  },
  {
    key: "last_downloaded_at",
    label: t("settings.downloads-column-last"),
    width: "minmax(0, 1fr)",
    align: "end",
    skeletonWidth: 110,
  },
]);

// Positional rank; the backend already returns the list sorted desc.
const rankOf = computed(() => {
  const map = new Map<number, number>();
  props.roms.forEach((rom, index) => map.set(rom.rom_id, index + 1));
  return map;
});

function openRom(rom: TopDownloadedRom) {
  router.push({ name: ROUTES.ROM, params: { rom: rom.rom_id } });
}
</script>

<template>
  <SettingsSection
    :title="t('settings.downloads-top')"
    icon="mdi-trophy-outline"
  >
    <RTable
      :columns="columns"
      :items="roms"
      :item-key="(r) => (r as TopDownloadedRom).rom_id"
      :loading="loading"
      clickable-rows
      min-width="720px"
      empty-icon="mdi-download-off-outline"
      :empty-message="t('settings.downloads-top-empty')"
      @row:click="(row) => openRom(row as TopDownloadedRom)"
    >
      <template #cell.rank="{ row }">
        <span class="r-v2-dl-top__rank">
          {{ rankOf.get((row as TopDownloadedRom).rom_id) }}
        </span>
      </template>
      <template #cell.rom_name="{ row }">
        <span class="r-v2-dl-top__name">
          {{ (row as TopDownloadedRom).rom_name }}
        </span>
      </template>
      <template #cell.platform_name="{ row }">
        <span class="r-v2-dl-top__meta">
          {{ (row as TopDownloadedRom).platform_name }}
        </span>
      </template>
      <template #cell.download_count="{ row }">
        <span class="r-v2-dl-top__count">
          <RIcon icon="mdi-download" size="14" />
          {{ (row as TopDownloadedRom).download_count.toLocaleString() }}
        </span>
      </template>
      <template #cell.file_size_bytes="{ row }">
        <span class="r-v2-dl-top__meta">
          {{ formatBytes((row as TopDownloadedRom).file_size_bytes, 1) }}
        </span>
      </template>
      <template #cell.last_downloaded_at="{ row }">
        <span class="r-v2-dl-top__meta">
          {{
            formatTimestamp(
              (row as TopDownloadedRom).last_downloaded_at,
              locale,
            )
          }}
        </span>
      </template>
    </RTable>
  </SettingsSection>
</template>

<style scoped>
.r-v2-dl-top__rank {
  font-variant-numeric: tabular-nums;
  font-weight: var(--r-font-weight-bold);
  color: var(--r-color-fg-faint);
}

.r-v2-dl-top__name {
  font-weight: var(--r-font-weight-semibold);
  color: var(--r-color-fg);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.r-v2-dl-top__meta {
  color: var(--r-color-fg-muted);
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}

.r-v2-dl-top__count {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-weight: var(--r-font-weight-bold);
  color: var(--r-color-brand-primary);
  font-variant-numeric: tabular-nums;
}
</style>
