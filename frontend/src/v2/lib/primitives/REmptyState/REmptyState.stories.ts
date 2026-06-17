import type { Meta, StoryObj } from "@storybook/vue3-vite";
import RBtn from "../RBtn/RBtn.vue";
import REmptyState from "./REmptyState.vue";

const meta: Meta<typeof REmptyState> = {
  title: "Primitives/REmptyState",
  component: REmptyState,
  argTypes: {
    icon: { control: "text" },
    title: { control: "text" },
    hint: { control: "text" },
    iconSize: { control: "text" },
    size: {
      control: "select",
      options: ["x-small", "small", "default", "large", "x-large"],
    },
  },
  render: (args) => ({
    components: { REmptyState },
    setup: () => ({ args }),
    template: `<REmptyState v-bind="args" />`,
  }),
};

export default meta;
type Story = StoryObj<typeof REmptyState>;

export const Default: Story = {
  args: {
    icon: "mdi-tray-remove",
    title: "Nothing here yet",
    hint: "Once you add something it will show up in this list.",
  },
};

export const Compact: Story = {
  args: {
    size: "small",
    icon: "mdi-music-note-outline",
    title: "No tracks",
  },
};

export const WithActions: Story = {
  args: {
    icon: "mdi-book-open-page-variant-outline",
    title: "No manual yet",
    hint: "Upload a PDF or re-download from the metadata source.",
  },
  render: (args) => ({
    components: { REmptyState, RBtn },
    setup: () => ({ args }),
    template: `
      <REmptyState v-bind="args">
        <template #actions>
          <RBtn prepend-icon="mdi-cloud-upload-outline">Upload</RBtn>
          <RBtn variant="outlined" prepend-icon="mdi-cloud-download-outline">Re-download</RBtn>
        </template>
      </REmptyState>
    `,
  }),
};
