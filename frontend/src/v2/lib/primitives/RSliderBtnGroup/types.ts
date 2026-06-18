export interface SliderBtnGroupItem<T extends string | number> {
  id: T;
  label?: string;
  icon?: string;
  to?: string;
  ariaLabel?: string;
  title?: string;
  disabled?: boolean;
}
