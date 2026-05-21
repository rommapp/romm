import type { Meta, StoryObj } from "@storybook/vue3-vite";
import { ref } from "vue";
import RTabNav from "./RTabNav.vue";

const meta: Meta<typeof RTabNav> = {
  title: "Primitives/RTabNav",
  component: RTabNav,
  argTypes: {
    size: {
      control: "select",
      options: ["x-small", "small", "default", "large", "x-large"],
    },
    variant: { control: "select", options: ["underlined", "pill"] },
    orientation: { control: "select", options: ["horizontal", "vertical"] },
  },
  render: (args) => ({
    components: { RTabNav },
    setup: () => {
      const active = ref(args.modelValue ?? "overview");
      return { args, active };
    },
    template: `<RTabNav v-bind="args" v-model="active" />`,
  }),
};

export default meta;
type Story = StoryObj<typeof RTabNav>;

export const Default: Story = {
  args: {
    modelValue: "overview",
    items: [
      { id: "overview", label: "Overview" },
      { id: "media", label: "Media" },
      { id: "notes", label: "Notes" },
    ],
  },
};

export const WithBadges: Story = {
  args: {
    modelValue: "achievements",
    items: [
      { id: "overview", label: "Overview" },
      { id: "achievements", label: "Achievements", badge: "12/40" },
      { id: "save-data", label: "Save data", badge: 7 },
      { id: "metadata", label: "Metadata" },
    ],
  },
};

export const Subtabs: Story = {
  args: {
    size: "small",
    modelValue: "saves",
    items: [
      { id: "saves", label: "Saves", badge: 5 },
      { id: "states", label: "States", badge: 2 },
    ],
  },
};

// Vertical pill variant — stacked menu items with optional leading
// icon. Used by SaveDataTab for the left-rail subtab nav.
export const VerticalPill: Story = {
  args: {
    variant: "pill",
    orientation: "vertical",
    modelValue: "saves",
    items: [
      {
        id: "saves",
        label: "Saves",
        icon: "mdi-content-save-outline",
        badge: 5,
      },
      {
        id: "states",
        label: "States",
        icon: "mdi-camera-outline",
        badge: 2,
      },
    ],
  },
  render: (args) => ({
    components: { RTabNav },
    setup: () => {
      const active = ref(args.modelValue ?? "saves");
      return { args, active };
    },
    template: `<div style="width: 200px;">
      <RTabNav v-bind="args" v-model="active" />
    </div>`,
  }),
};

export const HiddenItems: Story = {
  args: {
    modelValue: "overview",
    items: [
      { id: "overview", label: "Overview" },
      { id: "achievements", label: "Achievements", show: false },
      { id: "metadata", label: "Metadata" },
    ],
  },
};

// Image variant — items can carry a logo / brand mark via the `image`
// field instead of an MDI icon. Mirrors the per-provider raw-metadata
// tabs in EditRomDialog (IGDB / MobyGames / etc).
export const WithImages: Story = {
  args: {
    size: "small",
    modelValue: "details",
    items: [
      {
        id: "details",
        label: "Additional details",
        icon: "mdi-text-box-plus-outline",
      },
      { id: "ids", label: "Metadata IDs", icon: "mdi-database" },
      { id: "igdb", label: "IGDB", image: "/assets/scrappers/igdb.png" },
      {
        id: "moby",
        label: "MobyGames",
        image: "/assets/scrappers/moby.png",
      },
      {
        id: "ss",
        label: "ScreenScraper",
        image: "/assets/scrappers/ss.png",
      },
    ],
  },
};
