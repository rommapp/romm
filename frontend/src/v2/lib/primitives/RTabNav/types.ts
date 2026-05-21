export type RTabNavItem = {
  id: string;
  label: string;
  /** Optional MDI icon name shown before the label. */
  icon?: string;
  /** Optional image URL shown before the label — used when an item needs
   *  a logo / provider mark instead of a glyph (provider chips, brand
   *  tabs). Wins over `icon` when both are set. Rendered as an `<img>`
   *  sized to match the icon's visual weight. */
  image?: string;
  badge?: string | number | null;
  show?: boolean;
};
