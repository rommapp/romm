// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type RSelectRule = (value: any) => true | string;

export interface RSelectProps<Item, Model> {
  /** Typed by the bound ref; RSelect trusts it matches the items' keys. */
  modelValue?: Model;
  items?: readonly Item[];
  label?: string;
  placeholder?: string;
  variant?: "outlined" | "filled" | "underlined" | "plain";
  density?: "default" | "comfortable" | "compact";
  itemTitle?: string | ((item: Item) => string);
  itemValue?: string | ((item: Item) => unknown);
  multiple?: boolean;
  /** When true, the model holds the raw item objects instead of their
   *  `itemValue` keys. Read paths (selection comparisons, chip
   *  rendering, isSelected) are mode-agnostic: only emits change. */
  returnObject?: boolean;
  chips?: boolean;
  closableChips?: boolean;
  clearable?: boolean;
  disabled?: boolean;
  readonly?: boolean;
  loading?: boolean;
  hideDetails?: boolean | "auto";
  required?: boolean;
  prependInnerIcon?: string;
  appendInnerIcon?: string;
  rules?: RSelectRule[];
  hint?: string;
  error?: boolean;
  errorMessages?: string | string[];
  /** "stacked": label above; "inline": label as a left well. */
  prefixLabel?: "stacked" | "inline";
  /** Accent for focus + selected items. Defaults to brand-primary. */
  color?: string;
  /** Adds a sticky search input at the top of the panel that filters
   *  items locally by title. */
  searchable?: boolean;
  /** v-model:search: current query string. */
  search?: string;
  searchPlaceholder?: string;
  /** Where to place the menu relative to the activator. */
  menuLocation?:
    "bottom" | "top" | "bottom start" | "bottom end" | "top start" | "top end";
  /** Px gap between activator and menu. */
  menuOffset?: number;
  /** Hard cap on visible chips (defaults to ∞). Overflow is otherwise
   *  computed dynamically based on the activator's actual width. */
  maxVisibleChips?: number;
  /** Tone passed to the chip RTag (and its measurement mirror).
   *  Defaults to `brand`; pass `plain` to strip the chip chrome
   *  (PlatformSelect uses this so icon-only chips don't drown the
   *  field in coloured pills). */
  chipTone?:
    | "neutral"
    | "brand"
    | "accent"
    | "success"
    | "danger"
    | "warning"
    | "info"
    | "plain";
  /** Multi-select only: render a synthetic "All" row at the top of the
   *  menu (with a divider below) that toggles every item on / off. When
   *  no items are selected and this is on, the activator displays the
   *  `allOptionLabel` text instead of the placeholder, the empty
   *  selection reads as "every item" rather than "nothing picked". */
  showAllOption?: boolean;
  /** Label used by the "All" row in the menu and as the activator
   *  display when nothing is selected. Defaults to "All". */
  allOptionLabel?: string;
  /** Items it matches get a divider below their row, setting them apart
   *  from the ones that follow. */
  dividerAfter?: (item: Item) => boolean;
  /** Tip revealed from an info icon in the trailing label well. */
  info?: string;
}
