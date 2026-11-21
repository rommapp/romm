import type { Meta, StoryObj } from "@storybook/vue3-vite";
import { ref } from "vue";
import RBtn from "../RBtn/RBtn.vue";
import RSteps from "./RSteps.vue";

const meta: Meta<typeof RSteps> = {
  title: "Primitives/RSteps",
  component: RSteps,
  argTypes: {
    current: { control: { type: "number", min: 1, max: 5 } },
    total: { control: { type: "number", min: 2, max: 6 } },
    direction: { control: "select", options: ["forward", "back"] },
    lineWidth: { control: { type: "number", min: 16, max: 120 } },
    dotSize: { control: { type: "number", min: 20, max: 64 } },
  },
};

export default meta;

type Story = StoryObj<typeof RSteps>;

export const ThreeSteps: Story = {
  args: { current: 1, total: 3, direction: "forward" },
  render: (args) => ({
    components: { RSteps },
    setup: () => ({ args }),
    template: `<RSteps v-bind="args" />`,
  }),
};

export const Labelled: Story = {
  args: { current: 2, direction: "forward" },
  render: (args) => ({
    components: { RSteps },
    setup: () => ({
      args,
      steps: [{ label: "Library" }, { label: "Admin" }, { label: "Sources" }],
    }),
    template: `<RSteps v-bind="args" :steps="steps" />`,
  }),
};

export const Interactive: Story = {
  args: { total: 3, direction: "forward" },
  render: (args) => ({
    components: { RSteps, RBtn },
    setup: () => {
      const current = ref(1);
      const direction = ref<"forward" | "back">("forward");
      function go(delta: number) {
        const next = current.value + delta;
        if (next < 1 || next > 3) return;
        direction.value = delta > 0 ? "forward" : "back";
        current.value = next;
      }
      return { args, current, direction, go };
    },
    template: `
      <div style="display: flex; flex-direction: column; align-items: center; gap: 24px;">
        <RSteps v-bind="args" :current="current" :direction="direction" />
        <div style="display: flex; gap: 8px;">
          <RBtn variant="text" prepend-icon="mdi-chevron-left" :disabled="current === 1" @click="go(-1)">Previous</RBtn>
          <RBtn variant="flat" color="primary" append-icon="mdi-chevron-right" :disabled="current === 3" @click="go(1)">Next</RBtn>
        </div>
      </div>
    `,
  }),
};
