import type { Meta, StoryObj } from "@storybook/vue3-vite";
import { RBtn, RTextField } from "@v2/lib";
import { expect } from "storybook/test";
import { ref } from "vue";
import { useSpatialNav } from "@/v2/composables/useSpatialNav";
import {
  PlaygroundCallout,
  pressKey,
  useFocusReadout,
} from "./playground.fixtures";

// Pad arrows can't be reproduced in a play() -- the pad branch in useSpatialNav only fires for
// events dispatched by useGamepad. The pad path stays interactive only.

const meta: Meta = {
  title: "Input Navigation/Text fields",
  parameters: {
    layout: "padded",
    docs: {
      description: {
        component: `
On a **keyboard**, arrow keys inside a text field behave natively (caret movement, no spatial nav).

On a **controller D-pad**, Left/Right step the caret and exit at the text's end. Up/Down always move focus out.
This is the feature added by [\`useSpatialNav\` L171](frontend/src/v2/composables/useSpatialNav/index.ts#L171).

The pad path cannot be tested in \`play()\` because \`isPadEvent\` only tags synthetic events that \`useGamepad\` dispatches; connect a real controller to explore it interactively.
For unit coverage see \`useSpatialNav/index.test.ts\` ("text fields" describe block).
        `.trim(),
      },
    },
  },
  render: () => ({
    components: { RBtn, RTextField, PlaygroundCallout },
    setup() {
      useSpatialNav().install();
      return {
        text: ref("hello world"),
        notes: ref("line one\nline two"),
        count: ref(4),
        focused: useFocusReadout(),
      };
    },
    template: `
      <div style="display: grid; gap: var(--r-space-5); max-width: 640px">
        <PlaygroundCallout title="Text fields and the D-pad" :keys="['🎮 ←','🎮 →','🎮 ↑','🎮 ↓']">
          On a controller, Left and Right move the cursor and step out at the ends. Up and Down always leave.
          Your keyboard keeps working normally.
        </PlaygroundCallout>

        <div style="display: flex; align-items: center; gap: var(--r-space-3)">
          <RBtn data-label="Before" variant="translucent">Before</RBtn>
          <RTextField v-model="text" label="Game title" data-label="Title" style="flex: 1" />
          <RBtn data-label="After" variant="translucent">After</RBtn>
        </div>

        <label style="display: grid; gap: var(--r-space-1); color: var(--r-color-fg-secondary)">
          Notes
          <textarea
            v-model="notes"
            data-label="Notes"
            rows="3"
            style="
              background: var(--r-color-surface);
              color: var(--r-color-fg);
              border: 1px solid var(--r-color-border);
              border-radius: var(--r-radius-md);
              padding: var(--r-space-2) var(--r-space-3);
              font-family: inherit;
              font-size: inherit;
              resize: vertical;
            "
          ></textarea>
        </label>

        <label style="display: grid; gap: var(--r-space-1); color: var(--r-color-fg-secondary)">
          Players
          <input
            v-model.number="count"
            type="number"
            data-label="Players"
            style="
              background: var(--r-color-surface);
              color: var(--r-color-fg);
              border: 1px solid var(--r-color-border);
              border-radius: var(--r-radius-md);
              padding: var(--r-space-2) var(--r-space-3);
              font-family: inherit;
              font-size: inherit;
            "
          />
        </label>

        <p style="margin: 0; color: var(--r-color-fg-muted)">Focused: {{ focused }}</p>
      </div>`,
  }),
};

export default meta;

export const Interactive: StoryObj = {};

// Keyboard arrows stay native inside a text field -- spatial nav must not claim them.
export const KeyboardArrowsStayInField: StoryObj = {
  globals: { input: "key" },
  play: async ({ canvasElement }) => {
    // RTextField wraps a native <input>; find the first non-number input
    const input = canvasElement.querySelector<HTMLInputElement>(
      "input:not([type=number])",
    )!;
    input.focus();
    input.setSelectionRange(input.value.length, input.value.length);
    // ArrowRight at the end: ownsArrowKeys -> useSpatialNav returns early, no preventDefault
    await expect(pressKey("ArrowRight").defaultPrevented).toBe(false);
    // ArrowDown: same -- keyboard arrows always native in a text field
    await expect(pressKey("ArrowDown").defaultPrevented).toBe(false);
    await expect(input).toHaveFocus();
  },
};
