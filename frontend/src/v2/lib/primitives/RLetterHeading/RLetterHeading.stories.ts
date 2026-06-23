import type { Meta, StoryObj } from "@storybook/vue3-vite";
import RLetterHeading from "./RLetterHeading.vue";

const meta: Meta<typeof RLetterHeading> = {
  title: "Primitives/RLetterHeading",
  component: RLetterHeading,
  argTypes: {
    label: { control: "text" },
  },
  render: (args) => ({
    components: { RLetterHeading },
    setup: () => ({ args }),
    template: `<RLetterHeading v-bind="args" />`,
  }),
};

export default meta;
type Story = StoryObj<typeof RLetterHeading>;

export const Letter: Story = {
  args: { label: "A" },
};

export const Digits: Story = {
  args: { label: "#" },
};

// Default slot wins over the prop — useful when the label needs custom
// content (extra spacing, a count, etc.).
export const SlotContent: Story = {
  render: (args) => ({
    components: { RLetterHeading },
    setup: () => ({ args }),
    template: `<RLetterHeading v-bind="args">M &middot; 12 items</RLetterHeading>`,
  }),
  args: {},
};
