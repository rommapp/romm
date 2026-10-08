import type { Meta, StoryObj } from "@storybook/vue3-vite";
import { expect, waitFor } from "storybook/test";
import { romFixture } from "@/utils/rom.fixtures";
import { colorCoverArt } from "@/v2/tokens";
import GameCover from "./GameCover.vue";

// Two real images, so the browser makes a real srcset pick at this screen's density.
const image = (fill: string) =>
  URL.createObjectURL(
    new Blob(
      [
        `<svg xmlns="http://www.w3.org/2000/svg" width="2" height="3"><rect width="2" height="3" fill="${fill}"/></svg>`,
      ],
      { type: "image/svg+xml" },
    ),
  );

const small = image(colorCoverArt.base);
const large = image(colorCoverArt.warm);

const rom = romFixture({
  path_cover_small: small,
  path_cover_large: large,
  ss_metadata: null,
  gamelist_metadata: null,
});

const meta: Meta<typeof GameCover> = {
  title: "Media/GameCover",
  component: GameCover,
};

export default meta;

type Story = StoryObj<typeof GameCover>;

const coverImg = (canvasElement: HTMLElement) =>
  canvasElement.querySelector<HTMLImageElement>("img.game-cover__img");

/** The browser takes the small cover at 1x or below and the large one above. */
export const CoverForScreenDensity: Story = {
  name: "Cover for screen density",
  render: () => ({
    components: { GameCover },
    setup: () => ({ rom }),
    template: `<div style="width:160px"><GameCover :rom="rom" title="Chrono Trigger" :webp="false" responsive /></div>`,
  }),
  play: async ({ canvasElement }) => {
    await waitFor(() =>
      expect(coverImg(canvasElement)?.currentSrc).toBeTruthy(),
    );

    await expect(coverImg(canvasElement)?.currentSrc).toBe(
      window.devicePixelRatio <= 1 ? small : large,
    );
    await expect(coverImg(canvasElement)?.getAttribute("srcset")).toBe(
      `${small} 1x, ${large} 2x`,
    );
  },
};

/** Without `responsive` the slot always loads the large cover. */
export const LargeCoverByDefault: Story = {
  name: "Large cover by default",
  render: () => ({
    components: { GameCover },
    setup: () => ({ rom }),
    template: `<div style="width:160px"><GameCover :rom="rom" title="Chrono Trigger" :webp="false" /></div>`,
  }),
  play: async ({ canvasElement }) => {
    await waitFor(() =>
      expect(coverImg(canvasElement)?.currentSrc).toBeTruthy(),
    );

    await expect(coverImg(canvasElement)?.hasAttribute("srcset")).toBe(false);
    await expect(coverImg(canvasElement)?.currentSrc).toBe(large);
  },
};
