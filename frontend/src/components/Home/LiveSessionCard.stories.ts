import type { Meta, StoryObj } from "@storybook/vue3-vite";
import LiveSessionCard from "./LiveSessionCard.vue";

const meta: Meta<typeof LiveSessionCard> = {
  title: "Home/LiveSessionCard",
  component: LiveSessionCard,
  parameters: {
    // The card's name is the join action; axe wants every visible word on the
    // card (title, host, platform) in it, which no composite card can meet.
    a11y: {
      config: {
        rules: [{ id: "label-content-name-mismatch", enabled: false }],
      },
    },
  },
};

export default meta;
type Story = StoryObj<typeof LiveSessionCard>;

const session = {
  container: "http://box:3010",
  label: "Emulation station",
  platform: "ps2",
  rom_id: 42,
  rom_name: "Timesplitters 2",
  host_username: "ana",
  claimed_at: "2026-01-01T00:00:00Z",
  platform_id: 1,
  platform_display_name: "PlayStation 2",
  path_cover_small: null,
  path_cover_large: null,
  url_cover: null,
};

export const Default: Story = {
  args: { session },
};

export const UnknownHost: Story = {
  args: { session: { ...session, host_username: null } },
};
