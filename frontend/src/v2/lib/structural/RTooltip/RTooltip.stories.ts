import type { Meta, StoryObj } from "@storybook/vue3-vite";
import RBtn from "@/v2/lib/primitives/RBtn/RBtn.vue";
import RTooltip from "./RTooltip.vue";

const meta: Meta<typeof RTooltip> = {
  title: "Structural/RTooltip",
  component: RTooltip,
  argTypes: {
    text: { control: "text" },
    location: {
      control: "select",
      options: [
        "top",
        "bottom",
        "start",
        "end",
        "top start",
        "top end",
        "bottom start",
        "bottom end",
      ],
    },
    openDelay: { control: "number" },
    closeDelay: { control: "number" },
    offset: { control: "number" },
    contentClass: { control: "text" },
  },
};

export default meta;

type Story = StoryObj<typeof RTooltip>;

export const OnButton: Story = {
  args: { text: "Save your progress", location: "top" },
  render: (args) => ({
    components: { RTooltip, RBtn },
    setup: () => ({ args }),
    template: `
      <div class="r-v2 r-v2-dark" style="padding: 48px; background: #07070f;">
        <RTooltip v-bind="args">
          <template #activator="{ props }">
            <RBtn v-bind="props" prepend-icon="mdi-content-save">Save</RBtn>
          </template>
        </RTooltip>
      </div>
    `,
  }),
};

export const Locations: Story = {
  render: () => ({
    components: { RTooltip, RBtn },
    template: `
      <div class="r-v2 r-v2-dark" style="padding: 80px; background: #07070f; display: flex; gap: 24px; flex-wrap: wrap;">
        <RTooltip text="Tooltip on top" location="top">
          <template #activator="{ props }">
            <RBtn v-bind="props" icon="mdi-arrow-up" />
          </template>
        </RTooltip>
        <RTooltip text="Tooltip on end" location="end">
          <template #activator="{ props }">
            <RBtn v-bind="props" icon="mdi-arrow-right" />
          </template>
        </RTooltip>
        <RTooltip text="Tooltip on bottom" location="bottom">
          <template #activator="{ props }">
            <RBtn v-bind="props" icon="mdi-arrow-down" />
          </template>
        </RTooltip>
        <RTooltip text="Tooltip on start" location="start">
          <template #activator="{ props }">
            <RBtn v-bind="props" icon="mdi-arrow-left" />
          </template>
        </RTooltip>
      </div>
    `,
  }),
};

export const ParentAttach: Story = {
  render: () => ({
    components: { RTooltip, RBtn },
    template: `
      <div class="r-v2 r-v2-dark" style="padding: 48px; background: #07070f;">
        <RBtn icon="mdi-delete" variant="translucent">
          <RTooltip activator="parent" text="Delete this item" location="top" />
        </RBtn>
      </div>
    `,
  }),
};

export const LongText: Story = {
  args: {
    text: "Scans the selected library path, matches any new ROMs against the configured metadata providers, and refreshes artwork for existing entries.",
    location: "top",
  },
  render: (args) => ({
    components: { RTooltip, RBtn },
    setup: () => ({ args }),
    template: `
      <div class="r-v2 r-v2-dark" style="padding: 80px; background: #07070f;">
        <RTooltip v-bind="args">
          <template #activator="{ props }">
            <RBtn v-bind="props" prepend-icon="mdi-refresh">Full scan</RBtn>
          </template>
        </RTooltip>
      </div>
    `,
  }),
};
