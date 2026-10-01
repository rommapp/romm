import type { Meta, StoryObj } from "@storybook/vue3-vite";
import { RBtn } from "@v2/lib";
import { useSpatialNav } from "@/v2/composables/useSpatialNav";
import { PlaygroundCallout, useFocusReadout } from "./playground.fixtures";

// No play() -- useSpatialNav's pickSpatialTarget needs real layout (zero rects in happy-dom).

const meta: Meta = {
  title: "Input Navigation/Arrows find the nearest",
  parameters: {
    layout: "padded",
    docs: {
      description: {
        component:
          "A control straight ahead beats a nearer one off to the side. Diagonals are picked only when nothing lies ahead. See `spatialNav.ts` `spatialScore` for the full formula.",
      },
    },
  },
  render: () => ({
    components: { RBtn, PlaygroundCallout },
    setup() {
      useSpatialNav().install();
      const focused = useFocusReadout();
      return { focused };
    },
    template: `
      <div style="display: grid; gap: var(--r-space-5); max-width: 600px">
        <PlaygroundCallout title="Arrows find the nearest" :keys="['←','↑','→','↓']">
          Use the arrows to hop between buttons. RomM picks the closest one in the direction you press,
          wherever it sits on screen.
        </PlaygroundCallout>
        <div style="
          display: grid;
          grid-template-columns: repeat(4, 120px);
          gap: var(--r-space-8);
          position: relative;
        ">
          <RBtn data-label="A" variant="translucent" style="grid-column: 1; grid-row: 1">A</RBtn>
          <RBtn data-label="B" variant="translucent" style="grid-column: 3; grid-row: 1">B</RBtn>
          <RBtn data-label="C" variant="translucent" style="grid-column: 2; grid-row: 2; margin-top: 40px">C</RBtn>
          <RBtn data-label="D" variant="translucent" style="grid-column: 4; grid-row: 2">D</RBtn>
          <RBtn data-label="E" variant="translucent" style="grid-column: 1; grid-row: 3">E</RBtn>
          <RBtn data-label="F" variant="translucent" style="grid-column: 3; grid-row: 3; margin-top: 20px">F</RBtn>
          <RBtn data-label="G" variant="translucent" style="grid-column: 2; grid-row: 4">G</RBtn>
        </div>
        <p style="margin: 0; color: var(--r-color-fg-muted)">Focused: {{ focused }}</p>
      </div>`,
  }),
};

export default meta;
export const Interactive: StoryObj = {};
