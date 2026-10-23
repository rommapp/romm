// Shared definition of the three per-user ROM metrics (completion,
// rating, difficulty). Single source of truth consumed by both the
// desktop ribbon pills (GameActions) and the mobile status-sheet
// sections (GameMetricsSections), so their icons/accents/ranges never
// drift. Writes go through useGameActions.setScore(field, value).
export type MetricField = "completion" | "rating" | "difficulty";

export interface MetricConfig {
  field: MetricField;
  /** `percent` → 0..100 slider; `rating` → 1..max icon row. */
  kind: "rating" | "percent";
  /** i18n key for the metric's label. */
  labelKey: string;
  iconFull: string;
  iconEmpty: string;
  /** Token name (without the `--r-color-` prefix). */
  accent: string;
  /** Slider step; only meaningful for `percent`. */
  step: number;
}

export const METRICS: MetricConfig[] = [
  {
    field: "completion",
    kind: "percent",
    labelKey: "rom.metric-completion",
    iconFull: "mdi-progress-check",
    iconEmpty: "mdi-progress-helper",
    accent: "brand-primary",
    step: 5,
  },
  {
    field: "rating",
    kind: "rating",
    labelKey: "rom.metric-rating",
    iconFull: "mdi-star",
    iconEmpty: "mdi-star-outline",
    accent: "warning",
    step: 1,
  },
  {
    field: "difficulty",
    kind: "rating",
    labelKey: "rom.metric-difficulty",
    iconFull: "mdi-chili-mild",
    iconEmpty: "mdi-chili-mild-outline",
    accent: "danger",
    step: 1,
  },
];
