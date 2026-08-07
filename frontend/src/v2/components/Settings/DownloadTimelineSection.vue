<script setup lang="ts">
// DownloadTimelineSection. Daily download volume as a bare CSS bar
// chart. Deliberately dependency-free: the series is short (<= 365
// points) and a real charting library would be the heaviest thing on
// the settings route for one sparkline.
import { RIcon, RTooltip } from "@v2/lib";
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import type { DownloadTimelinePoint } from "@/__generated__";
import { formatBytes } from "@/utils";
import SettingsSection from "@/v2/components/Settings/SettingsSection.vue";

defineOptions({ inheritAttrs: false });

interface Props {
  timeline: readonly DownloadTimelinePoint[];
}
const props = defineProps<Props>();

const { t, locale } = useI18n();

const peak = computed(() =>
  props.timeline.reduce((max, p) => Math.max(max, p.count), 0),
);

const hasAny = computed(() => peak.value > 0);

// Floor at 4% so a day with a single download still paints something.
function barHeight(count: number): string {
  if (!peak.value) return "0%";
  return `${Math.max(4, (count / peak.value) * 100)}%`;
}

function formatDay(iso: string): string {
  return new Date(`${iso}T00:00:00`).toLocaleDateString(
    locale.value.replace("_", "-"),
    { month: "short", day: "numeric" },
  );
}

// Only label the ends and the midpoint. A tick per day is unreadable.
const axisLabels = computed(() => {
  const points = props.timeline;
  if (points.length === 0) return [];
  const mid = Math.floor(points.length / 2);
  return [
    { key: "start", label: formatDay(points[0].date) },
    { key: "mid", label: formatDay(points[mid].date) },
    { key: "end", label: formatDay(points[points.length - 1].date) },
  ];
});
</script>

<template>
  <SettingsSection
    :title="t('settings.downloads-over-time')"
    icon="mdi-chart-timeline-variant"
  >
    <div class="r-v2-dl-timeline">
      <div v-if="!hasAny" class="r-v2-dl-timeline__empty">
        <RIcon icon="mdi-chart-line-variant" size="22" />
        <span>{{ t("settings.downloads-none-in-window") }}</span>
      </div>
      <template v-else>
        <div class="r-v2-dl-timeline__chart">
          <RTooltip v-for="point in timeline" :key="point.date">
            <template #activator="{ props: tipProps }">
              <div v-bind="tipProps" class="r-v2-dl-timeline__col">
                <div
                  class="r-v2-dl-timeline__bar"
                  :class="{ 'r-v2-dl-timeline__bar--zero': point.count === 0 }"
                  :style="{ height: barHeight(point.count) }"
                />
              </div>
            </template>
            <span>
              {{ formatDay(point.date) }} ·
              {{ t("settings.downloads-count", { count: point.count }) }}
              <template v-if="point.size_bytes > 0">
                · {{ formatBytes(point.size_bytes, 1) }}
              </template>
            </span>
          </RTooltip>
        </div>
        <div class="r-v2-dl-timeline__axis">
          <span v-for="tick in axisLabels" :key="tick.key">{{
            tick.label
          }}</span>
        </div>
      </template>
    </div>
  </SettingsSection>
</template>

<style scoped>
.r-v2-dl-timeline {
  padding: 16px;
}

.r-v2-dl-timeline__chart {
  display: flex;
  align-items: flex-end;
  gap: 2px;
  height: 140px;
}

.r-v2-dl-timeline__col {
  flex: 1 1 0;
  min-width: 0;
  height: 100%;
  display: flex;
  align-items: flex-end;
}

.r-v2-dl-timeline__bar {
  width: 100%;
  border-radius: 2px 2px 0 0;
  background: var(--r-color-brand-primary);
  transition: background var(--r-motion-fast) var(--r-motion-ease-out);
}

.r-v2-dl-timeline__col:hover .r-v2-dl-timeline__bar {
  background: var(--r-color-fg);
}

.r-v2-dl-timeline__bar--zero {
  background: var(--r-color-border);
}

.r-v2-dl-timeline__axis {
  display: flex;
  justify-content: space-between;
  margin-top: 8px;
  font-size: 11px;
  color: var(--r-color-fg-faint);
}

.r-v2-dl-timeline__empty {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 24px;
  color: var(--r-color-fg-muted);
}
</style>
