import type { Meta, StoryObj } from "@storybook/vue3-vite";
import RSpinner from "./RSpinner.vue";

const meta: Meta<typeof RSpinner> = {
  title: "Primitives/RSpinner",
  component: RSpinner,
  argTypes: {
    size: { control: "number" },
    width: { control: "number" },
    color: { control: "text" },
  },
};

export default meta;

type Story = StoryObj<typeof RSpinner>;

export const Inline: Story = {
  render: () => ({
    components: { RSpinner },
    template: `
      <div style="display:flex;gap:1rem;align-items:center;color:var(--r-color-fg)">
        <RSpinner /> Loading library…
      </div>
    `,
  }),
};

export const Large: Story = { args: { size: 48, width: 4 } };
