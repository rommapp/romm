<script setup lang="ts">
// The scrolling band of track details under a now-playing caption, led by the
// queue position; it is empty only while no track is shown.
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import { RChip, RMarquee } from "@/lib";
import type { NowPlayingTags } from "@/utils/soundtrackTracks";

defineOptions({ inheritAttrs: false });

const props = defineProps<{
  tags?: NowPlayingTags | undefined;
  /** One-based position of the track in the queue. */
  position: number;
  total: number;
}>();

const { t } = useI18n();

type Chip = { icon: string; label: string; color?: string };

const chips = computed<Chip[]>(() => {
  if (props.position <= 0 || props.total <= 0) return [];
  const tags = props.tags;
  const list: Chip[] = [
    {
      icon: "mdi-playlist-music",
      label: `${props.position.toLocaleString()} / ${props.total.toLocaleString()}`,
    },
  ];
  // The caption shows the artist itself when there is no album.
  if (tags?.album && tags.artist)
    list.push({ icon: "mdi-account-music", label: tags.artist });
  if (tags?.year)
    list.push({
      icon: "mdi-calendar",
      label: String(tags.year),
      color: "accent",
    });
  if (tags?.genre)
    list.push({ icon: "mdi-music-clef-treble", label: tags.genre });
  if (tags?.track)
    list.push({
      icon: "mdi-numeric",
      label: t("rom.chip-track-n", { n: tags.track }),
    });
  if (tags?.disc)
    list.push({
      icon: "mdi-disc",
      label: t("rom.chip-disc-n", { n: tags.disc }),
    });
  return list;
});
</script>

<template>
  <RMarquee class="r-np-chips" v-bind="$attrs">
    <div class="r-np-chips__row">
      <RChip
        v-for="chip in chips"
        :key="chip.icon"
        size="small"
        variant="translucent"
        :color="chip.color"
        :prepend-icon="chip.icon"
      >
        {{ chip.label }}
      </RChip>
    </div>
  </RMarquee>
</template>

<style scoped>
/* Holds a small chip's height even before there is a track. */
.r-np-chips {
  min-height: 24px;
}

.r-np-chips__row {
  display: flex;
  gap: var(--r-space-1);
}
</style>
