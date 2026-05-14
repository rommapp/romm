import type { Meta, StoryObj } from "@storybook/vue3-vite";
import { ref } from "vue";
import RRating from "./RRating.vue";

const meta: Meta<typeof RRating> = {
  title: "Forms/RRating",
  component: RRating,
  argTypes: {
    length: { control: "number" },
    size: { control: "text" },
    color: { control: "text" },
    activeColor: { control: "text" },
    emptyIcon: { control: "text" },
    fullIcon: { control: "text" },
    density: {
      control: "select",
      options: ["default", "comfortable", "compact"],
    },
    readonly: { control: "boolean" },
    halfIncrements: { control: "boolean" },
    hover: { control: "boolean" },
    clearable: { control: "boolean" },
  },
  render: (args) => ({
    components: { RRating },
    setup: () => {
      const value = ref(3.5);
      return { args, value };
    },
    template: `<RRating v-bind="args" v-model="value" />`,
  }),
};

export default meta;

type Story = StoryObj<typeof RRating>;

export const Default: Story = { args: { halfIncrements: true, hover: true } };
export const Readonly: Story = { args: { readonly: true } };
export const Large: Story = { args: { size: "large" } };

// Difficulty preset — same primitive driven by props. Exercises the
// new emptyIcon/fullIcon/activeColor pass-through used by the
// score-picker on GameDetails.
export const Difficulty: Story = {
  args: {
    length: 10,
    hover: true,
    clearable: true,
    emptyIcon: "mdi-chili-mild-outline",
    fullIcon: "mdi-chili-mild",
    color: "danger",
    activeColor: "danger",
    size: "small",
  },
};

// Rating preset — 10 stars, gold accent, the shape consumed by the
// score-picker for "Your Rating".
export const RatingTen: Story = {
  args: {
    length: 10,
    hover: true,
    clearable: true,
    color: "warning",
    activeColor: "warning",
    size: "small",
  },
};
