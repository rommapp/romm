import type { Meta, StoryObj } from "@storybook/vue3-vite";
import { RBtn } from "@v2/lib";
import { expect } from "storybook/test";
import { onBeforeUnmount, onMounted, ref } from "vue";
import { byLabel, PlaygroundCallout } from "./playground.fixtures";

const meta: Meta = {
  title: "Input Navigation/Focus follows you",
  parameters: {
    layout: "padded",
    docs: {
      description: {
        component:
          "Primitives style focus with `html[data-input='key'] .x:focus-visible` and `html[data-input='pad'] .x:focus-visible`, never a bare `:focus`. Modality changes appearance, never size.",
      },
    },
  },
  render: () => ({
    components: { RBtn, PlaygroundCallout },
    setup() {
      const input = ref(document.documentElement.dataset.input ?? "mouse");
      const sync = () =>
        (input.value = document.documentElement.dataset.input ?? "mouse");
      const observer = new MutationObserver(sync);
      onMounted(() =>
        observer.observe(document.documentElement, {
          attributes: true,
          attributeFilter: ["data-input"],
        }),
      );
      onBeforeUnmount(() => observer.disconnect());
      return { input };
    },
    template: `
      <div style="display: grid; gap: var(--r-space-5)">
        <PlaygroundCallout title="Focus follows you" :keys="['Tab','←','→']">
          Press Tab or an arrow key and a ring shows where you are. Click with the mouse and it hides.
          RomM only shows focus when you need it.
        </PlaygroundCallout>
        <div style="display: flex; gap: var(--r-space-3)">
          <RBtn data-label="Library" variant="translucent">Library</RBtn>
          <RBtn data-label="Collections" variant="translucent">Collections</RBtn>
          <RBtn data-label="Search" variant="translucent">Search</RBtn>
        </div>
        <p data-testid="data-input" style="margin: 0; color: var(--r-color-fg-muted)">
          &lt;html data-input="{{ input }}"&gt;
        </p>
      </div>`,
  }),
};

export default meta;

export const Interactive: StoryObj = {};

export const RingShowsForKeyboard: StoryObj = {
  globals: { input: "key" },
  play: async ({ canvasElement }) => {
    await expect(document.documentElement.dataset.input).toBe("key");
    byLabel(canvasElement, "Library").focus();
    await expect(byLabel(canvasElement, "Library")).toHaveFocus();
  },
};

export const RingHidesForMouse: StoryObj = {
  globals: { input: "mouse" },
  play: async () => {
    await expect(document.documentElement.dataset.input).toBe("mouse");
  },
};
