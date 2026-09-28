import type { Meta, StoryObj } from "@storybook/vue3-vite";
import { makeSave } from "@/v2/utils/saveStates.fixtures";
import AssetChips from "./AssetChips.vue";

// Chip content per prop is covered by AssetChips.test.ts.
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
  args: { asset: makeSave(1, "main_quest", 2) },
};

export const Latest: Story = {
  name: "Latest tag",
  args: { asset: makeSave(1, "autosave", 1), latest: true },
};

export const NoEmulator: Story = {
  name: "No emulator on asset",
  args: { asset: makeSave(1, null, 5, { emulator: null }) },
};

export const HideEmulatorChip: Story = {
  name: "showEmulator false",
  args: { asset: makeSave(1, "main_quest", 2), showEmulator: false },
};
