import type { Meta, StoryObj } from "@storybook/vue3-vite";
import { RBtn } from "@v2/lib";
import { expect } from "storybook/test";
import { ref } from "vue";
import { useGridNav } from "@/v2/composables/useGridNav";
import { useSpatialNav } from "@/v2/composables/useSpatialNav";
import {
  byLabel,
  PlaygroundCallout,
  pressKey,
  useFocusReadout,
} from "./playground.fixtures";

const meta: Meta = {
  title: "Input Navigation/Action ribbon",
  parameters: {
    layout: "padded",
    docs: {
      description: {
        component:
          "Claim keys you handle with `preventDefault()`. Leave the edges unclaimed, and useSpatialNav carries focus to the next region.",
      },
    },
  },
  render: () => ({
    components: { RBtn, PlaygroundCallout },
    setup() {
      const ribbon = ref<HTMLElement | null>(null);
      useGridNav(ribbon, {
        getRows: () => (ribbon.value ? [ribbon.value] : []),
        getCells: (row) =>
          Array.from(row.querySelectorAll<HTMLElement>(".pg-action")),
      });
      useSpatialNav().install();
      return { ribbon, focused: useFocusReadout() };
    },
    template: `
      <div style="display: grid; gap: var(--r-space-6); max-width: 640px">
        <PlaygroundCallout title="Try:" :keys="['←','→','↓']">
          Arrow through the ribbon with Left / Right. Press Down from the ribbon -- two systems hand off here.
        </PlaygroundCallout>

        <div ref="ribbon" style="display: flex; gap: var(--r-space-2)">
          <RBtn class="pg-action" data-label="Play" variant="translucent">Play</RBtn>
          <RBtn class="pg-action" data-label="Download" variant="translucent">Download</RBtn>
          <RBtn class="pg-action" data-label="Favorite" variant="translucent">Favorite</RBtn>
          <RBtn class="pg-action" data-label="More" variant="translucent">More</RBtn>
        </div>

        <div style="margin-top: var(--r-space-8); display: flex; gap: var(--r-space-2)">
          <RBtn data-label="Overview" variant="text">Overview</RBtn>
          <RBtn data-label="Files" variant="text">Files</RBtn>
          <RBtn data-label="Notes" variant="text">Notes</RBtn>
        </div>

        <p style="margin: 0; color: var(--r-color-fg-muted)">Focused: {{ focused }}</p>
      </div>`,
  }),
};

export default meta;

export const Interactive: StoryObj = {};

export const EdgeKeyIsUnclaimed: StoryObj = {
  globals: { input: "key" },
  play: async ({ canvasElement }) => {
    byLabel(canvasElement, "Play").focus();
    const inside = pressKey("ArrowRight");
    // useGridNav claimed ArrowRight (moved to Download)
    await expect(inside.defaultPrevented).toBe(true);
    await expect(byLabel(canvasElement, "Download")).toHaveFocus();

    byLabel(canvasElement, "More").focus();
    const edge = pressKey("ArrowRight");
    // ArrowRight at the last cell is left unclaimed for useSpatialNav
    await expect(edge.defaultPrevented).toBe(false);
  },
};
