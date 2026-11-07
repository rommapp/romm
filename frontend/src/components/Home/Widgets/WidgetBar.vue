<script setup lang="ts">
// WidgetBar: horizontal scrollable rail of Home widgets. The render
// order is driven by `widgetOrder` (user-reorderable from Settings →
// Home → Widgets), the visible set by per-widget toggles. The rail
// itself disappears when every widget is off: no empty rail taking
// up vertical space.
import { computed, watch } from "vue";
import { useUISettings } from "@/composables/useUISettings";
import storeActivity from "@/stores/activity";
import { parseWidgetOrder, WIDGETS } from "./widgets";

defineOptions({ inheritAttrs: false });

const settings = useUISettings();
const { libraryStatsMode, widgetOrder, widgetPlayingNow } = settings;
const activityStore = storeActivity();

// The bar, not the card, keeps the activity list live: the card is unmounted
// while nobody is playing, so it can't be the one listening for a session.
watch(
  widgetPlayingNow,
  (enabled) => {
    if (!enabled) return;
    activityStore.initSocket();
    void activityStore.fetchAll();
  },
  { immediate: true },
);

const statsMode = computed<"compact" | "extended">(() =>
  libraryStatsMode.value === "extended" ? "extended" : "compact",
);

// Materialize the ordered list of currently-enabled widgets. Each
// entry pairs the registry def with the component-specific props
// needed by the bar's render loop.
const orderedWidgets = computed(() => {
  const order = parseWidgetOrder(widgetOrder.value);
  return order
    .map((id) => WIDGETS.find((w) => w.id === id))
    .filter((w): w is (typeof WIDGETS)[number] => Boolean(w))
    .filter((w) => Boolean(settings[w.enabledKey].value))
    .filter((w) => w.id !== "playingNow" || activityStore.activeCount > 0);
});

function widgetProps(id: string): Record<string, unknown> {
  if (id === "libraryStats") return { mode: statsMode.value };
  return {};
}

const anyEnabled = computed(() => orderedWidgets.value.length > 0);
</script>

<template>
  <div v-if="anyEnabled" class="r-widget-bar">
    <component
      :is="w.component"
      v-for="w in orderedWidgets"
      :key="w.id"
      v-bind="widgetProps(w.id)"
    />
  </div>
</template>

<style scoped>
.r-widget-bar {
  display: flex;
  gap: 14px;
  flex-wrap: nowrap;
  /* Extra bottom padding so the rail breathes before the first
     CardRow underneath (Continue playing / Recently added). */
  padding: 16px var(--r-row-pad) 24px;
  overflow-x: auto;
  overflow-y: visible;
  scrollbar-width: none;
}
.r-widget-bar::-webkit-scrollbar {
  display: none;
}
/* A widget can hide its own card (Anniversaries on an empty day) while staying
   mounted, so a rail with no cards collapses rather than leaving its padding. */
.r-widget-bar:not(:has(> *)) {
  display: none;
}
</style>
