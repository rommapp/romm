import { MINIMAL_VIEWPORTS, type ViewportMap } from "storybook/viewport";

/**
 * RomM v2 breakpoints match useBreakpoint (xs <600, sm-and-down ≤959.98, md ≥960).
 * CSS that targets html[data-bp~="xs"] only applies when the iframe is under 600px wide
 * (RomM phone preset, or Storybook Small mobile at 320×568).
 */
export const ROMM_DEVICE_VIEWPORTS = {
  rommPhoneXs: {
    name: "390×844 · RomM phone (xs, <600)",
    styles: { width: "390px", height: "844px" },
    type: "mobile",
  },
  rommTabletSm: {
    name: "768×1024 · RomM tablet (sm-and-down, <960)",
    styles: { width: "768px", height: "1024px" },
    type: "tablet",
  },
  rommDesktopMd: {
    name: "1280×800 · RomM desktop (md+, ≥960)",
    styles: { width: "1280px", height: "800px" },
    type: "desktop",
  },
  steamDeck: {
    name: "1280×800 · Steam Deck (landscape)",
    styles: { width: "1280px", height: "800px" },
    type: "other",
  },
  aynThorTop: {
    name: "1920×1080 · AYN Thor top screen (landscape)",
    styles: { width: "1920px", height: "1080px" },
    type: "other",
  },
  aynThorBottom: {
    name: "1240×1080 · AYN Thor bottom screen (landscape)",
    styles: { width: "1240px", height: "1080px" },
    type: "other",
  },
} as const satisfies ViewportMap;

/** Storybook minimal presets plus RomM tiers, Steam Deck, and AYN Thor screens. */
export const ROMM_STORYBOOK_VIEWPORTS: ViewportMap = {
  ...MINIMAL_VIEWPORTS,
  ...ROMM_DEVICE_VIEWPORTS,
};
