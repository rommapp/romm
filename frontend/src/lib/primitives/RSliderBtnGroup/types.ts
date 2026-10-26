export interface SliderBtnGroupItem<T extends string | number> {
  id: T;
  label?: string;
  icon?: string;
  /** Optional count rendered as a pill after the label (e.g. number of
   *  saves/states). Hidden when null/undefined or 0. */
  badge?: string | number | null;
  to?: string;
  ariaLabel?: string;
  title?: string;
  disabled?: boolean;
}
