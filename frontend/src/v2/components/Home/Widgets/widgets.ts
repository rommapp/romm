// Home widget registry — single source of truth for the set of
// widgets the rail can render, the toggle that controls each one, and
// the labels surfaced in the reorder list inside Settings. Adding a
// new widget is: ship the component, append a `WidgetDef` entry here,
// add the toggle key in `useUISettings`. Both the `WidgetBar` and the
// settings reorder list pick it up automatically.
import type { Component } from "vue";
import LibraryStatsWidget from "./LibraryStatsWidget.vue";
import RandomPickWidget from "./RandomPickWidget.vue";

export type WidgetId = "randomPick" | "libraryStats";

export interface WidgetDef {
  id: WidgetId;
  /** The component to render. */
  component: Component;
  /** Key in `useUISettings` that controls visibility. */
  enabledKey: "widgetRandomPick" | "widgetLibraryStats";
  /** i18n key for the user-facing label (settings reorder list). */
  labelKey: string;
  /** Optional MDI icon used in the reorder list. */
  icon: string;
}

export const WIDGETS: readonly WidgetDef[] = [
  {
    id: "randomPick",
    component: RandomPickWidget,
    enabledKey: "widgetRandomPick",
    labelKey: "settings.widget-random-pick",
    icon: "mdi-dice-multiple-outline",
  },
  {
    id: "libraryStats",
    component: LibraryStatsWidget,
    enabledKey: "widgetLibraryStats",
    labelKey: "settings.widget-library-stats",
    icon: "mdi-chart-box-outline",
  },
];

const WIDGET_IDS = new Set<WidgetId>(WIDGETS.map((w) => w.id));

/** Parses the comma-separated `widgetOrder` setting, drops unknown
 *  IDs, and appends any widgets the user hasn't ranked yet so newly
 *  shipped widgets surface at the end without manual reordering. */
export function parseWidgetOrder(raw: string): WidgetId[] {
  const seen = new Set<WidgetId>();
  const result: WidgetId[] = [];
  for (const part of raw.split(",")) {
    const id = part.trim() as WidgetId;
    if (WIDGET_IDS.has(id) && !seen.has(id)) {
      seen.add(id);
      result.push(id);
    }
  }
  for (const w of WIDGETS) {
    if (!seen.has(w.id)) result.push(w.id);
  }
  return result;
}

/** Inverse of `parseWidgetOrder` — joins back to the storage format. */
export function serializeWidgetOrder(order: readonly WidgetId[]): string {
  return order.join(",");
}
