import type { Meta, StoryObj } from "@storybook/vue3-vite";
import { RBtn } from "@v2/lib";
import { ref } from "vue";
import { useSpatialNav } from "@/v2/composables/useSpatialNav";
import { useWrapGridNav } from "@/v2/composables/useWrapGridNav";
import {
  labels,
  PlaygroundCallout,
  useFocusReadout,
} from "./playground.fixtures";

// No play() -- useWrapGridNav rebuilds rows from getBoundingClientRect, which happy-dom doesn't provide.

const meta: Meta = {
  title: "Input Navigation/Grouped wrap grid",
  parameters: {
    layout: "padded",
    docs: {
      description: {
        component:
          "Rows come from each tile's on-screen position, so the column count, and where Down lands, follow the viewport. Resize the Storybook iframe to see it change.",
      },
    },
  },
  render: () => ({
    components: { RBtn, PlaygroundCallout },
    setup() {
      const root = ref<HTMLElement | null>(null);
      useWrapGridNav(root, { cellSelector: ".pg-tile" });
      useSpatialNav().install();
      return {
        root,
        groupA: labels("Nintendo", 7),
        groupB: labels("Sega", 3),
        focused: useFocusReadout(),
      };
    },
    template: `
      <div style="display: grid; gap: var(--r-space-5)">
        <PlaygroundCallout title="Try:" :keys="['←','↑','→','↓']">
          Press Down from Group A's last row, then resize the viewport toolbar width to see where Down lands change.
        </PlaygroundCallout>
        <div ref="root">
          <h2 style="font-size: 1rem; color: var(--r-color-fg-muted); margin: 0 0 var(--r-space-3)">Nintendo</h2>
          <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: var(--r-space-3); margin-bottom: var(--r-space-6)">
            <RBtn
              v-for="l in groupA" :key="l"
              class="pg-tile"
              :data-label="l"
              variant="translucent"
              style="height: 80px"
            >{{ l }}</RBtn>
          </div>
          <h2 style="font-size: 1rem; color: var(--r-color-fg-muted); margin: 0 0 var(--r-space-3)">Sega</h2>
          <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: var(--r-space-3)">
            <RBtn
              v-for="l in groupB" :key="l"
              class="pg-tile"
              :data-label="l"
              variant="translucent"
              style="height: 80px"
            >{{ l }}</RBtn>
          </div>
        </div>
        <p style="margin: 0; color: var(--r-color-fg-muted)">Focused: {{ focused }}</p>
      </div>`,
  }),
};

export default meta;
export const Interactive: StoryObj = {};
