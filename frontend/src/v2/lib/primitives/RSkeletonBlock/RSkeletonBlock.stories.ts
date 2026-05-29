import type { Meta, StoryObj } from "@storybook/vue3-vite";
import RSkeletonBlock from "./RSkeletonBlock.vue";

const meta: Meta<typeof RSkeletonBlock> = {
  title: "Primitives/RSkeletonBlock",
  component: RSkeletonBlock,
  argTypes: {
    width: { control: "text" },
    height: { control: "text" },
    rounded: {
      control: "select",
      options: ["sm", "md", "lg", "xl", "full"],
    },
    circle: { control: "boolean" },
  },
};

export default meta;

type Story = StoryObj<typeof RSkeletonBlock>;

export const Line: Story = {
  args: { width: 240, height: 16 },
};

export const Card: Story = {
  render: () => ({
    components: { RSkeletonBlock },
    template: `
      <div style="display:flex;flex-direction:column;gap:.75rem;width:240px">
        <RSkeletonBlock :width="240" :height="180" rounded="md" />
        <RSkeletonBlock :width="180" :height="16" />
        <RSkeletonBlock :width="120" :height="14" />
      </div>
    `,
  }),
};

export const Avatar: Story = {
  args: { width: 40, height: 40, circle: true },
};
