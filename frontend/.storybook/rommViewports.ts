import { MINIMAL_VIEWPORTS, type ViewportMap } from "storybook/viewport";
import { ROMM_DEVICES } from "../src/v2/devices";

/** Storybook minimal presets plus one per useBreakpoint tier and the target handhelds. */
export const ROMM_STORYBOOK_VIEWPORTS = {
  ...MINIMAL_VIEWPORTS,
  ...Object.fromEntries(
    Object.entries(ROMM_DEVICES).map(([key, device]) => [
      key,
      {
        name: device.label,
        styles: { width: `${device.width}px`, height: `${device.height}px` },
        type: device.type,
      },
    ]),
  ),
} satisfies ViewportMap;
