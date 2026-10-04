import type { Meta, StoryObj } from "@storybook/vue3-vite";
import RSectionLabel from "./RSectionLabel.vue";

const meta: Meta<typeof RSectionLabel> = {
  title: "Primitives/RSectionLabel",
  component: RSectionLabel,
  argTypes: {
    size: { control: "select", options: ["sm", "md"] },
    tone: { control: "select", options: ["muted", "faint", "secondary"] },
    icon: { control: "text" },
    as: { control: "text" },
  },
  args: { size: "md", tone: "muted", as: "h3" },
};

export default meta;

type Story = StoryObj<typeof RSectionLabel>;

export const Default: Story = {
  render: (args) => ({
    components: { RSectionLabel },
    setup: () => ({ args }),
    template: `<RSectionLabel v-bind="args">Metadata sources</RSectionLabel>`,
  }),
};

export const Tones: Story = {
  render: () => ({
    components: { RSectionLabel },
    template: `
      <div style="display:flex;flex-direction:column;gap:12px">
        <RSectionLabel tone="muted">Muted (default)</RSectionLabel>
        <RSectionLabel tone="faint">Faint</RSectionLabel>
        <RSectionLabel tone="secondary">Secondary</RSectionLabel>
      </div>`,
  }),
};

export const Sizes: Story = {
  render: () => ({
    components: { RSectionLabel },
    template: `
      <div style="display:flex;flex-direction:column;gap:12px">
        <RSectionLabel size="md" icon="mdi-database-search">Medium (default)</RSectionLabel>
        <RSectionLabel size="sm" icon="mdi-database-search">Small</RSectionLabel>
      </div>`,
  }),
};

export const Light: Story = {
  ...Tones,
  globals: { theme: "light" },
};
