import { MINIMAL_VIEWPORTS, type ViewportMap } from "storybook/viewport";

/** One preset per useBreakpoint tier (xs <600, sm <960, md <1280), plus handhelds. */
const ROMM_DEVICE_VIEWPORTS = {
  rommPhoneXs: {
    name: "390×844 · RomM phone (xs, <600)",
    styles: { width: "390px", height: "844px" },
    type: "mobile",
  },
  rommTabletSm: {
    name: "768×1024 · RomM tablet (sm, 600–959)",
    styles: { width: "768px", height: "1024px" },
    type: "tablet",
  },
  rommDesktopMd: {
    name: "1024×768 · RomM desktop (md, 960–1279)",
    styles: { width: "1024px", height: "768px" },
    type: "desktop",
  },
  steamDeck: {
    name: "1280×800 · Steam Deck (lg, landscape)",
    styles: { width: "1280px", height: "800px" },
    type: "other",
  },
  aynThorTop: {
    name: "1920×1080 · AYN Thor top screen (xl, landscape)",
    styles: { width: "1920px", height: "1080px" },
    type: "other",
  },
  aynThorBottom: {
    name: "1240×1080 · AYN Thor bottom screen (md, landscape)",
    styles: { width: "1240px", height: "1080px" },
    type: "other",
  },
} satisfies ViewportMap;

export const ROMM_STORYBOOK_VIEWPORTS: ViewportMap = {
  ...MINIMAL_VIEWPORTS,
  ...ROMM_DEVICE_VIEWPORTS,
};
