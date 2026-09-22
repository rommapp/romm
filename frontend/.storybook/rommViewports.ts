import { MINIMAL_VIEWPORTS, type ViewportMap } from "storybook/viewport";

/**
 * RomM v2 breakpoints match useBreakpoint (xs <600, sm-and-down ≤959.98, md ≥960).
 * CSS that targets html[data-bp~="xs"] (e.g. compact AssetList rows) only applies when
 * the preview iframe is narrower than 600px, so use "RomM phone (xs)" or resize below 600.
 */
export const ROMM_DEVICE_VIEWPORTS = {
  rommPhoneXs: {
    name: "RomM phone (xs, <600)",
    styles: { width: "390px", height: "844px" },
    type: "mobile",
  },
  rommTabletSm: {
    name: "RomM tablet (sm-and-down, <960)",
    styles: { width: "768px", height: "1024px" },
    type: "tablet",
  },
  rommDesktopMd: {
    name: "RomM desktop (md+, ≥960)",
    styles: { width: "1280px", height: "800px" },
    type: "desktop",
  },
  steamDeck: {
    name: "Steam Deck (1280×800)",
    styles: { width: "1280px", height: "800px" },
    type: "other",
  },
  aynThorTop: {
    name: "AYN Thor top screen (1080×1920)",
    styles: { width: "1080px", height: "1920px" },
    type: "mobile",
  },
  switchHandheld: {
    name: "Nintendo Switch handheld (1280×720)",
    styles: { width: "1280px", height: "720px" },
    type: "other",
  },
} as const satisfies ViewportMap;

/** Storybook toolbar presets: stock minimal set plus RomM breakpoints and common handhelds. */
export const ROMM_STORYBOOK_VIEWPORTS: ViewportMap = {
  ...MINIMAL_VIEWPORTS,
  ...ROMM_DEVICE_VIEWPORTS,
};
