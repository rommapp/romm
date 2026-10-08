import type { Meta, StoryObj } from "@storybook/vue3-vite";
import { expect, waitFor } from "storybook/test";
import { romFixture } from "@/utils/rom.fixtures";
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

const small = image("#3b82f6");
const large = image("#f97316");

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

/** At 1x or below the browser takes the small cover, not the large `src`. */
export const SmallCoverAtLowDensity: Story = {
  name: "Small cover at low density",
  render: () => ({
    components: { GameCover },
    setup: () => ({ rom }),
    template: `<div style="width:160px"><GameCover :rom="rom" title="Chrono Trigger" :webp="false" responsive /></div>`,
  }),
  play: async ({ canvasElement }) => {
    const img = () =>
      canvasElement.querySelector<HTMLImageElement>("img.game-cover__img");
    await waitFor(() => expect(img()?.currentSrc).toBeTruthy());

    await expect(window.devicePixelRatio).toBeLessThanOrEqual(1);
    await expect(img()?.currentSrc).toBe(small);
    await expect(img()?.getAttribute("srcset")).toBe(
      `${small} 1x, ${large} 2x`,
    );
  },
};
