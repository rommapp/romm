<script setup lang="ts">
// CardFlags — region / language emoji chips over the cover's bottom-left
// corner, the v2 counterpart of v1's cover flags. Visibility is driven by
// the showRegions / showLanguages UI settings; each chip caps at three
// emoji and carries the full list in its hover title. Purely informational:
// pointer events pass through to the card, and the chips fade out under the
// hover overlay so they never collide with the action row.
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import { useUISettings } from "@/composables/useUISettings";
import type { SimpleRom } from "@/stores/roms";
import { languageToEmoji, regionToEmoji } from "@/utils";

const props = defineProps<{ rom: SimpleRom }>();

const { t } = useI18n();
const { showRegions, showLanguages } = useUISettings();

const regions = computed(() =>
  showRegions.value ? (props.rom.regions ?? []).filter(Boolean) : [],
);
const languages = computed(() =>
  showLanguages.value ? (props.rom.languages ?? []).filter(Boolean) : [],
);
</script>

<template>
  <div v-if="regions.length || languages.length" class="card-flags">
    <span
      v-if="regions.length"
      class="card-flags__chip"
      :title="`${t('rom.regions')}: ${regions.join(', ')}`"
    >
      <span v-for="region in regions.slice(0, 3)" :key="region">
        {{ regionToEmoji(region) }}
      </span>
    </span>
    <span
      v-if="languages.length"
      class="card-flags__chip"
      :title="`${t('rom.languages')}: ${languages.join(', ')}`"
    >
      <span v-for="language in languages.slice(0, 3)" :key="language">
        {{ languageToEmoji(language) }}
      </span>
    </span>
  </div>
</template>

<style scoped>
.card-flags {
  position: absolute;
  bottom: 7px;
  left: 7px;
  z-index: 2;
  display: flex;
  align-items: center;
  gap: 4px;
  max-width: calc(100% - 14px);
  pointer-events: none;
  transition: opacity 0.12s ease;
}

.card-flags__chip {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  padding: 2px 5px;
  background: var(--r-color-overlay-scrim-soft);
  border: 1px solid var(--r-color-overlay-border);
  border-radius: var(--r-radius-pill);
  font-size: 11px;
  line-height: 1.2;
  backdrop-filter: blur(6px);
}
</style>
