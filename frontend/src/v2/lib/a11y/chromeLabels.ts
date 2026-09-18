// Chrome labels — the accessible names for controls a primitive renders on
// its own behalf: a dialog's close button, a chip's remove affordance, a
// date field's month/year steppers.
//
// Primitives may not touch i18n, and these labels are not content the call
// site supplies: they belong to the primitive's own affordance, and a
// per-instance prop for each one would need passing at every call site to
// have any effect (the `closeLabel` / `clearLabel` props that predate this
// never were, so they rendered English everywhere). So the app injects one
// bundle and every primitive reads it. `inject` is plain Vue, so the
// library stays free of i18n.
//
// The provider supplies getters that resolve through i18n, which run inside
// the reading component's render effect, so a locale switch re-renders the
// labels with no refs to unwrap.
//
// Unprovided (a bare `mount`, a story without the decorator) the English
// defaults apply, so a primitive always has an accessible name.
import { inject } from "vue";
import type { InjectionKey } from "vue";

export interface ChromeLabels {
  /** Dismiss affordance on dialogs, drawers and the carousel. */
  close: string;
  /** Reset affordance on text, select and combobox fields. */
  clear: string;
  /** Per-item removal on chips and multi-select values. */
  remove: string;
  /** Select-all entry in a multi-select's option list. */
  all: string;
  /** Carousel step controls. */
  previous: string;
  next: string;
  /** Date field: the picker toggle, its steppers and the today shortcut. */
  datePicker: string;
  previousYear: string;
  previousMonth: string;
  nextMonth: string;
  nextYear: string;
  today: string;
}

export const DEFAULT_CHROME_LABELS: ChromeLabels = {
  close: "Close",
  clear: "Clear",
  remove: "Remove",
  all: "All",
  previous: "Previous",
  next: "Next",
  datePicker: "Date picker",
  previousYear: "Previous year",
  previousMonth: "Previous month",
  nextMonth: "Next month",
  nextYear: "Next year",
  today: "Today",
};

export const ChromeLabelsKey: InjectionKey<ChromeLabels> =
  Symbol("RChromeLabels");

/** Read the injected bundle, falling back to English. */
export function useChromeLabels(): ChromeLabels {
  return inject(ChromeLabelsKey, DEFAULT_CHROME_LABELS);
}
