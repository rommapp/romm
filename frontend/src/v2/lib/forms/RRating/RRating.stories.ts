import type { Meta, StoryObj } from "@storybook/vue3-vite";
import { expect, userEvent, within } from "storybook/test";
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

// Keyboard: Tab across the star buttons, Enter/Space commits the rating.
export const KeyboardNav: Story = {
  name: "Keyboard navigation (play)",
  args: { ariaLabel: "Rating" },
  render: (args) => ({
    components: { RRating },
    setup: () => {
      const value = ref(0);
      return { args, value };
    },
    template: `<RRating v-bind="args" v-model="value" />`,
  }),
  play: async ({ canvasElement, step }) => {
    const canvas = within(canvasElement);
    const stars = canvas.getAllByRole("radio");

    await step("Tab focuses the stars in order", async () => {
      await userEvent.tab();
      expect(stars[0]).toHaveFocus();
      await userEvent.tab();
      await userEvent.tab();
      expect(stars[2]).toHaveFocus();
    });

    await step("Enter commits the focused star as the rating", async () => {
      await userEvent.keyboard("{Enter}");
      expect(stars[2]).toHaveAttribute("aria-checked", "true");
      expect(stars[0]).toHaveAttribute("aria-checked", "false");
    });
  },
};

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
