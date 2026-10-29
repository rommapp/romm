// Prop vocabulary the primitives share: a `color` / `rounded` value names
// one of these, or passes any other CSS value straight through.

/** Tone names to theme colour tokens. */
export const TONE_MAP: Readonly<Record<string, string>> & {
  readonly primary: string;
  readonly error: string;
} = {
  primary: "var(--r-color-brand-primary)",
  secondary: "var(--r-color-brand-secondary)",
  accent: "var(--r-color-brand-accent)",
  success: "var(--r-color-success)",
  warning: "var(--r-color-warning)",
  danger: "var(--r-color-danger)",
  error: "var(--r-color-danger)",
  info: "var(--r-color-info)",
  "romm-red": "var(--r-color-romm-red)",
  "romm-green": "var(--r-color-romm-green)",
  "romm-blue": "var(--r-color-romm-blue)",
  "romm-gold": "var(--r-color-romm-gold)",
};

/** Corner radius names to lengths. */
export const ROUNDED_MAP: Readonly<Record<string, string>> = {
  "0": "0",
  sm: "4px",
  md: "8px",
  lg: "12px",
  xl: "16px",
  full: "999px",
  pill: "999px",
  circle: "50%",
};
