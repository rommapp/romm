import type { Meta, StoryObj } from "@storybook/vue3-vite";
import PlayModeBadge from "./PlayModeBadge.vue";

const meta: Meta<typeof PlayModeBadge> = {
  title: "Platforms/PlayModeBadge",
  component: PlayModeBadge,
};

export default meta;
type Story = StoryObj<typeof PlayModeBadge>;

export const Browser: Story = {
  args: { mode: "browser", emulator: "emulatorjs" },
};

export const Stream: Story = {
  args: { mode: "stream", streamLabel: "PCSX2" },
};

export const Both: Story = {
  args: { mode: "both", emulator: "emulatorjs", streamLabel: "RetroArch" },
};

export const Large: Story = {
  args: {
    mode: "both",
    emulator: "emulatorjs",
    streamLabel: "RetroArch",
    size: 96,
  },
};
