export type RSortDir = "asc" | "desc";

export interface RSortHeaderProps {
  label: string;
  /** Renders the label as a sort button. */
  sortable?: boolean | undefined;
  /** Whether this column is the one the list is sorted by. */
  active?: boolean | undefined;
  /** Direction of the active sort. */
  dir?: RSortDir | undefined;
  align?: "start" | "end" | "center" | undefined;
  /** Keeps the label for screen readers only, for icon or action columns. */
  hideLabel?: boolean | undefined;
}
