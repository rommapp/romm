<script setup lang="ts">
// FilesSummary: top-of-FilesTab card showing the ROM's name + total
// size + revision + ROM-level hashes (click-to-copy via HashChip).
// Carries the missing-from-fs flag when applicable.
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import type { DetailedRomSchema } from "@/__generated__";
import HashChip from "@/components/shared/HashChip.vue";
import LocationChip from "@/components/shared/LocationChip.vue";
import MissingFSBadge from "@/components/shared/MissingFSBadge.vue";
import { RIcon } from "@/lib";
import { formatBytes } from "@/utils";

defineOptions({ inheritAttrs: false });

const { t } = useI18n();

const props = defineProps<{ rom: DetailedRomSchema }>();

const fileCount = computed(() => props.rom.files?.length ?? 0);

interface RomHash {
  label: string;
  value: string | null;
}
const hashes = computed<RomHash[]>(() => {
  // CHD SHA-1 lives on the file, not the ROM: surface it at ROM level
  // only when the ROM is a single CHD file (mirrors v1's FileInfo).
  const chdSha1 = props.rom.has_simple_single_file
    ? (props.rom.files[0]?.chd_sha1_hash ?? null)
    : null;
  return [
    { label: "SHA-1", value: props.rom.sha1_hash },
    { label: "CHD SHA-1", value: chdSha1 },
    { label: "MD5", value: props.rom.md5_hash },
    { label: "CRC", value: props.rom.crc_hash },
    { label: "RA", value: props.rom.ra_hash },
  ].filter((h) => h.value);
});
</script>

<template>
  <section class="r-files-summary">
    <header class="r-files-summary__head">
      <div class="r-files-summary__title">
        <RIcon icon="mdi-folder-outline" size="18" />
        <span class="r-files-summary__name">{{ rom.fs_name }}</span>
        <MissingFSBadge
          v-if="rom.missing_from_fs"
          :text="
            t('rom.missing-from-fs-path', {
              path: `${rom.fs_path}/${rom.fs_name}`,
            })
          "
        />
      </div>
      <div class="r-files-summary__stats">
        <span>{{ fileCount }} file{{ fileCount === 1 ? "" : "s" }}</span>
        <span class="r-files-summary__sep">·</span>
        <span>{{ formatBytes(rom.fs_size_bytes) }}</span>
        <template v-if="rom.revision">
          <span class="r-files-summary__sep">·</span>
          <span>Rev. {{ rom.revision }}</span>
        </template>
      </div>
    </header>

    <div class="r-files-summary__location">
      <LocationChip :path="rom.full_path" />
    </div>

    <div v-if="hashes.length > 0" class="r-files-summary__hashes">
      <HashChip
        v-for="h in hashes"
        :key="h.label"
        :label="h.label"
        :value="h.value"
      />
    </div>
  </section>
</template>

<style scoped>
.r-files-summary {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 12px 14px;
  background: var(--r-color-bg-elevated);
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-md);
  flex-shrink: 0;
}
.r-files-summary__head {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.r-files-summary__title {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--r-color-fg);
  font-size: 13.5px;
  font-weight: var(--r-font-weight-medium);
  min-width: 0;
}
.r-files-summary__name {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.r-files-summary__stats {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11.5px;
  color: var(--r-color-fg-muted);
  flex-wrap: wrap;
}
.r-files-summary__sep {
  opacity: 0.5;
}
.r-files-summary__location {
  display: flex;
  min-width: 0;
}
.r-files-summary__hashes {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
}
</style>
