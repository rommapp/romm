// Accessible names for controls a primitive renders on its own behalf: a
// dialog's close button, a chip's remove X, a date field's steppers. Not
// caller-supplied content, and a per-instance prop for each would have to be
// passed at every call site to do anything (the `closeLabel` / `clearLabel`
// props that predate this never were, so they rendered English everywhere).
//
// So the app provides one bundle of i18n-backed getters, read during the
// consuming component's render so a locale switch propagates. `inject` is
// plain Vue, keeping the library free of i18n; unprovided, English applies.
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
