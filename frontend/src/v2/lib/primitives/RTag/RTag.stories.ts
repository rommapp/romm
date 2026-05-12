import type { Meta, StoryObj } from "@storybook/vue3-vite";
import RTag from "./RTag.vue";

const meta: Meta<typeof RTag> = {
  title: "Primitives/RTag",
  component: RTag,
  argTypes: {
    prependIcon: { control: "text" },
    appendIcon: { control: "text" },
    label: { control: "text" },
    text: { control: "text" },
    mono: { control: "boolean" },
    tone: {
      control: "select",
      options: [
        "neutral",
        "brand",
        "accent",
        "success",
        "danger",
        "warning",
        "info",
      ],
    },
    size: {
      control: "select",
      options: ["x-small", "small", "default", "large", "x-large"],
    },
  },
  render: (args) => ({
    components: { RTag },
    setup: () => ({ args }),
    template: `<RTag v-bind="args" />`,
  }),
};

export default meta;
type Story = StoryObj<typeof RTag>;

// Header tags — the "regions / languages / custom tags" row.
export const HeaderRegion: Story = {
  args: { text: "USA", tone: "info", size: "small" },
};
export const HeaderLanguage: Story = {
  args: { text: "EN", tone: "brand", size: "small" },
};
export const HeaderCustom: Story = {
  args: { text: "v4.1", size: "small" },
};

// Hash chip — eyebrow label + monospace value.
export const Hash: Story = {
  args: { label: "MD5", text: "5d41402abc4b2a76b9719d911017c592", mono: true },
};

// Verification badges — match uses success tone, miss stays neutral.
export const VerificationMatch: Story = {
  args: {
    prependIcon: "mdi-check-circle",
    text: "Redump",
    tone: "success",
  },
};
export const VerificationMiss: Story = {
  args: {
    prependIcon: "mdi-close-circle-outline",
    text: "TOSEC",
  },
};

// Slot fallback when text isn't enough.
export const SlotContent: Story = {
  render: (args) => ({
    components: { RTag },
    setup: () => ({ args }),
    template: `<RTag v-bind="args"><strong>Bold</strong>&nbsp;value</RTag>`,
  }),
  args: { tone: "warning" },
};
