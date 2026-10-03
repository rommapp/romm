import type { Meta, StoryObj } from "@storybook/vue3";
import { ref } from "vue";
import RSliderBtnGroup from "./RSliderBtnGroup.vue";

// Generic components can't fill Storybook's `component` slot, so it's cast;
// the instantiation types the stories' args.
const meta: Meta<typeof RSliderBtnGroup<string>> = {
  title: "Primitives/RSliderBtnGroup",
  component: RSliderBtnGroup as never,
  tags: ["autodocs"],
  argTypes: {
    variant: {
      control: "select",
      options: ["segmented", "tab"],
    },
    orientation: {
      control: "select",
      options: ["horizontal", "vertical"],
    },
    disabled: { control: "boolean" },
    ariaLabel: { control: "text" },
  },
  parameters: {
    docs: {
      description: {
        component:
          "Segmented control / tab pill with a sliding indicator. Consumer controls the active id via `v-model`; for nav-style tabs, items may declare a `to` path and render as router-links.",
      },
    },
  },
};
export default meta;

type Story = StoryObj;

export const Segmented: Story = {
  args: { variant: "segmented" },
  render: (args) => ({
    components: { RSliderBtnGroup },
    setup() {
      const layout = ref<"grid" | "list">("grid");
      return { args, layout };
    },
    template: `
      <RSliderBtnGroup
        v-bind="args"
        :model-value="layout"
        :items="[
          { id: 'grid', icon: 'mdi-view-grid-outline', ariaLabel: 'Grid', title: 'Grid' },
          { id: 'list', icon: 'mdi-view-list', ariaLabel: 'List', title: 'List' },
        ]"
        @update:model-value="(v) => (layout = v)"
      />
    `,
  }),
};

export const Tab: Story = {
  args: { variant: "tab" },
  render: (args) => ({
    components: { RSliderBtnGroup },
    setup() {
      const active = ref<"home" | "favorites" | "platforms">("home");
      return { args, active };
    },
    template: `
      <RSliderBtnGroup
        v-bind="args"
        :model-value="active"
        :items="[
          { id: 'home', label: 'Home' },
          { id: 'favorites', label: 'Favorites' },
          { id: 'platforms', label: 'Platforms' },
        ]"
        @update:model-value="(v) => (active = v)"
      />
    `,
  }),
};

// Compact tab pill for a row in a list, such as a per-item mode toggle.
export const TabXSmall: Story = {
  args: { variant: "tab", size: "x-small" },
  render: (args) => ({
    components: { RSliderBtnGroup },
    setup() {
      const active = ref<"hide" | "allow">("hide");
      return { args, active };
    },
    template: `
      <RSliderBtnGroup
        v-bind="args"
        :model-value="active"
        :items="[
          { id: 'hide', label: 'Hide', icon: 'mdi-eye-off-outline' },
          { id: 'allow', label: 'Allow', icon: 'mdi-check-decagram-outline' },
        ]"
        @update:model-value="(v) => (active = v)"
      />
    `,
  }),
};

// Vertical tab pill: same aesthetic and sliding indicator as the
// horizontal tab variant, just stacked.
export const VerticalTab: Story = {
  args: { variant: "tab", orientation: "vertical" },
  render: (args) => ({
    components: { RSliderBtnGroup },
    setup() {
      const tool = ref<"scan" | "upload" | "patcher">("scan");
      return { args, tool };
    },
    template: `
      <div style="display: inline-block;">
        <RSliderBtnGroup
          v-bind="args"
          :model-value="tool"
          :items="[
            { id: 'scan', icon: 'mdi-magnify-scan', label: 'Scan', ariaLabel: 'Scan' },
            { id: 'upload', icon: 'mdi-cloud-upload-outline', label: 'Upload', ariaLabel: 'Upload' },
            { id: 'patcher', icon: 'mdi-file-cog-outline', label: 'Patcher', ariaLabel: 'Patcher' },
          ]"
          style="min-width: 200px;"
          @update:model-value="(v) => (tool = v)"
        />
      </div>
    `,
  }),
  parameters: {
    docs: {
      description: {
        story:
          "Vertical orientation stacks items in a column with the indicator sliding along the Y axis. Identical visual language to the horizontal tab pill.",
      },
    },
  },
};

// Vertical segmented: icon-only column with the indicator following
// the active item. Useful as a side rail for view switchers.
export const VerticalSegmented: Story = {
  args: { variant: "segmented", orientation: "vertical" },
  render: (args) => ({
    components: { RSliderBtnGroup },
    setup() {
      const view = ref<"grid" | "list" | "compact">("grid");
      return { args, view };
    },
    template: `
      <RSliderBtnGroup
        v-bind="args"
        :model-value="view"
        :items="[
          { id: 'grid', icon: 'mdi-view-grid-outline', ariaLabel: 'Grid', title: 'Grid' },
          { id: 'list', icon: 'mdi-view-list', ariaLabel: 'List', title: 'List' },
          { id: 'compact', icon: 'mdi-view-sequential', ariaLabel: 'Compact', title: 'Compact' },
        ]"
        @update:model-value="(v) => (view = v)"
      />
    `,
  }),
};

export const Disabled: Story = {
  args: { variant: "segmented" },
  render: (args) => ({
    components: { RSliderBtnGroup },
    setup() {
      const group = ref<"none" | "letter">("none");
      return { args, group };
    },
    template: `
      <RSliderBtnGroup
        v-bind="args"
        :model-value="group"
        :items="[
          { id: 'none', icon: 'mdi-view-agenda-outline', ariaLabel: 'Flat' },
          { id: 'letter', icon: 'mdi-alphabetical-variant', ariaLabel: 'By letter', disabled: true },
        ]"
        @update:model-value="(v) => (group = v)"
      />
    `,
  }),
};
