// The devices v2 is built for: one per useBreakpoint tier plus the target
// handhelds. Single home for Storybook's viewport toolbar
// (.storybook/rommViewports.ts) and the Playwright device projects
// (playwright.config.ts).
export interface RommDevice {
  /** Plain name; `deviceProjectName()` adds its inputs for Playwright. */
  name: string;
  /** Storybook's viewport toolbar label. */
  label: string;
  width: number;
  height: number;
  /** Storybook's toolbar icon; `mobile` also means a phone-style browser. */
  type: "mobile" | "tablet" | "desktop" | "other";
  /** Has a touchscreen. */
  hasTouchHci: boolean;
  /** Has built-in game controls, so the UI should start in gamepad modality. */
  hasGamepadHci: boolean;
}

/** The Playwright project name: the device's name plus its inputs, so
 *  "Steam Deck (touch, gamepad)", or just the name when it has neither. Shown
 *  in VS Code's test panel and matched by `--project`. */
export function deviceProjectName(device: RommDevice): string {
  const inputs = [
    device.hasTouchHci && "touch",
    device.hasGamepadHci && "gamepad",
  ].filter(Boolean);
  return inputs.length ? `${device.name} (${inputs.join(", ")})` : device.name;
}

export const ROMM_DEVICES = {
  rommPhoneXs: {
    name: "Phone XS",
    label: "390×844 · RomM phone (xs)",
    width: 390,
    height: 844,
    type: "mobile",
    hasTouchHci: true,
    hasGamepadHci: false,
  },
  rommTabletSm: {
    name: "Tablet SM",
    label: "768×1024 · RomM tablet (sm)",
    width: 768,
    height: 1024,
    type: "tablet",
    hasTouchHci: true,
    hasGamepadHci: false,
  },
  rommDesktopMd: {
    name: "Desktop MD",
    label: "1024×768 · RomM desktop (md)",
    width: 1024,
    height: 768,
    type: "desktop",
    hasTouchHci: false,
    hasGamepadHci: false,
  },
  steamDeck: {
    name: "Steam Deck",
    label: "1280×800 · Steam Deck (lg, landscape)",
    width: 1280,
    height: 800,
    type: "other",
    hasTouchHci: true,
    hasGamepadHci: true,
  },
  aynThorTop: {
    name: "AYN Thor top screen",
    label: "1920×1080 · AYN Thor top screen (xl, landscape)",
    width: 1920,
    height: 1080,
    type: "other",
    hasTouchHci: true,
    hasGamepadHci: true,
  },
  aynThorBottom: {
    name: "AYN Thor bottom screen",
    label: "1240×1080 · AYN Thor bottom screen (md, landscape)",
    width: 1240,
    height: 1080,
    type: "other",
    hasTouchHci: true,
    hasGamepadHci: true,
  },
} as const satisfies Record<string, RommDevice>;
