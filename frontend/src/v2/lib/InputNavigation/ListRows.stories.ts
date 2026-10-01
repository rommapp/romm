import type { Meta, StoryObj } from "@storybook/vue3-vite";
import { RBtn } from "@v2/lib";
import { expect, userEvent } from "storybook/test";
import { ref } from "vue";
import { useGridNav } from "@/v2/composables/useGridNav";
import { useSpatialNav } from "@/v2/composables/useSpatialNav";
import {
  byLabel,
  PlaygroundCallout,
  useFocusReadout,
} from "./playground.fixtures";

const meta: Meta = {
  title: "Input Navigation/List rows",
  parameters: { layout: "padded" },
  render: () => ({
    components: { RBtn, PlaygroundCallout },
    setup() {
      const root = ref<HTMLElement | null>(null);
      useGridNav(root, {
        rowSelector: ".pg-row",
        getCells: (row) =>
          Array.from(
            row.querySelectorAll<HTMLElement>("a, button:not([disabled])"),
          ),
      });
      useSpatialNav().install();
      return { root, rows: [1, 2, 3, 4], focused: useFocusReadout() };
    },
    template: `
      <div style="display: grid; gap: var(--r-space-4); max-width: 560px">
        <PlaygroundCallout title="Try:" :keys="['→','↓']">Move right, then down. You stay in the Dismiss column.</PlaygroundCallout>
        <div ref="root" style="display: grid; gap: var(--r-space-2)">
          <div v-for="n in rows" :key="n" class="pg-row"
               style="display: flex; align-items: center; gap: var(--r-space-3); padding: var(--r-space-2) var(--r-space-3); border-radius: var(--r-radius-md); background: var(--r-color-surface)">
            <span style="flex: 1; color: var(--r-color-fg-secondary)">Notification {{ n }}</span>
            <RBtn :data-label="'Open ' + n" :aria-label="'Open notification ' + n" variant="text">Open</RBtn>
            <RBtn :data-label="'Dismiss ' + n" :aria-label="'Dismiss notification ' + n" variant="text" :disabled="n === 3">Dismiss</RBtn>
          </div>
        </div>
        <p data-testid="focused" style="margin: 0; color: var(--r-color-fg-muted)">Focused: {{ focused }}</p>
      </div>`,
  }),
};

export default meta;

export const Interactive: StoryObj = {};

export const KeepsColumnAcrossRows: StoryObj = {
  globals: { input: "key" },
  play: async ({ canvasElement }) => {
    byLabel(canvasElement, "Open 1").focus();
    await userEvent.keyboard("{ArrowRight}");
    await expect(byLabel(canvasElement, "Dismiss 1")).toHaveFocus();
    await userEvent.keyboard("{ArrowDown}");
    await expect(byLabel(canvasElement, "Dismiss 2")).toHaveFocus();
  },
};

export const SkipsDisabledCell: StoryObj = {
  globals: { input: "key" },
  play: async ({ canvasElement }) => {
    byLabel(canvasElement, "Open 2").focus();
    await userEvent.keyboard("{ArrowRight}"); // preferredCol = 1
    await userEvent.keyboard("{ArrowDown}"); // row 3 has Dismiss disabled -> clamped to Open 3
    await expect(byLabel(canvasElement, "Open 3")).toHaveFocus();
    await userEvent.keyboard("{ArrowDown}"); // preferredCol still 1
    await expect(byLabel(canvasElement, "Dismiss 4")).toHaveFocus();
  },
};
