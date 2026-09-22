import type { Meta, StoryObj } from "@storybook/vue3-vite";
import { expect } from "storybook/test";
import { makeSave } from "@/v2/utils/saveStateStoryFixtures";
import { canvas } from "@/v2/utils/saveStateStoryPlays";
import AssetChips from "./AssetChips.vue";

const meta: Meta<typeof AssetChips> = {
  title: "Shared/AssetChips",
  component: AssetChips,
  decorators: [
    () => ({
      template: `
        <div style="padding: 16px; background: var(--r-color-bg-elevated);">
          <story />
        </div>
      `,
    }),
  ],
};

export default meta;
type Story = StoryObj<typeof AssetChips>;

export const Default: Story = {
  name: "Emulator + size",
  render: () => ({
    components: { AssetChips },
    setup() {
      return { asset: makeSave(1, "main_quest", 2) };
    },
    template: `<AssetChips :asset="asset" />`,
  }),
  play: async ({ canvasElement, step }) => {
    await step("emulator tag and formatted size render", async () => {
      const ui = canvas(canvasElement);
      expect(ui.getByText("snes9x")).toBeTruthy();
      expect(ui.getByText("8 KB")).toBeTruthy();
    });
  },
};

export const Latest: Story = {
  name: "Latest tag",
  play: async ({ canvasElement, step }) => {
    await step("latest badge when requested", async () => {
      expect(canvas(canvasElement).getByText("Latest")).toBeTruthy();
    });
  },
  render: () => ({
    components: { AssetChips },
    setup() {
      return { asset: makeSave(1, "autosave", 1) };
    },
    template: `<AssetChips :asset="asset" latest />`,
  }),
};

export const NoEmulator: Story = {
  name: "No emulator on asset",
  render: () => ({
    components: { AssetChips },
    setup() {
      return { asset: makeSave(1, null, 5, { emulator: null }) };
    },
    template: `<AssetChips :asset="asset" />`,
  }),
};

export const HideEmulatorChip: Story = {
  name: "showEmulator false",
  render: () => ({
    components: { AssetChips },
    setup() {
      return { asset: makeSave(1, "main_quest", 2) };
    },
    template: `<AssetChips :asset="asset" :show-emulator="false" />`,
  }),
};
