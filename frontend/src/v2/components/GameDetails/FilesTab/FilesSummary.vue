<script setup lang="ts">
// FilesSummary — top-of-FilesTab card showing the ROM's name + total
// size + revision + ROM-level hashes (click-to-copy via HashChip).
// Carries the missing-from-fs flag when applicable.
import { RIcon } from "@v2/lib";
import { computed } from "vue";
import type { DetailedRomSchema } from "@/__generated__";
import { formatBytes } from "@/utils";
import HashChip from "@/v2/components/shared/HashChip.vue";
import MissingFSBadge from "@/v2/components/shared/MissingFSBadge.vue";

defineOptions({ inheritAttrs: false });

const props = defineProps<{ rom: DetailedRomSchema }>();

const fileCount = computed(() => props.rom.files?.length ?? 0);

interface RomHash {
  label: string;
  value: string | null;
}
const hashes = computed<RomHash[]>(() => {
  // CHD SHA-1 lives on the file, not the ROM — surface it at ROM level
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
  <section class="r-v2-files-summary">
    <header class="r-v2-files-summary__head">
      <div class="r-v2-files-summary__title">
        <RIcon icon="mdi-folder-outline" size="18" />
        <span class="r-v2-files-summary__name">{{ rom.fs_name }}</span>
        <MissingFSBadge
          v-if="rom.missing_from_fs"
          :text="`Missing from filesystem: ${rom.fs_path}/${rom.fs_name}`"
        />
      </div>
      <div class="r-v2-files-summary__stats">
        <span>{{ fileCount }} file{{ fileCount === 1 ? "" : "s" }}</span>
        <span class="r-v2-files-summary__sep">·</span>
        <span>{{ formatBytes(rom.fs_size_bytes) }}</span>
        <template v-if="rom.revision">
          <span class="r-v2-files-summary__sep">·</span>
          <span>Rev. {{ rom.revision }}</span>
        </template>
      </div>
    </header>

    <div v-if="hashes.length > 0" class="r-v2-files-summary__hashes">
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
.r-v2-files-summary {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 12px 14px;
  background: var(--r-color-bg-elevated);
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-md);
  flex-shrink: 0;
}
.r-v2-files-summary__head {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.r-v2-files-summary__title {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--r-color-fg);
  font-size: 13.5px;
  font-weight: var(--r-font-weight-medium);
  min-width: 0;
}
.r-v2-files-summary__name {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.r-v2-files-summary__stats {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11.5px;
  color: var(--r-color-fg-muted);
  flex-wrap: wrap;
}
.r-v2-files-summary__sep {
  opacity: 0.5;
}
.r-v2-files-summary__hashes {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
}
</style>
