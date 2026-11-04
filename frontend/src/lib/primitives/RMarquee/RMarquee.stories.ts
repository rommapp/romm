import type { Meta, StoryObj } from "@storybook/vue3-vite";
import RChip from "../RChip/RChip.vue";
import RMarquee from "./RMarquee.vue";

const meta: Meta<typeof RMarquee> = {
  title: "Primitives/RMarquee",
  component: RMarquee,
  argTypes: {
    speed: { control: { type: "number", min: 5, max: 200 } },
    gap: { control: { type: "number", min: 0, max: 120 } },
  },
  args: { speed: 30, gap: 32 },
};

export default meta;

type Story = StoryObj<typeof RMarquee>;

const chips = `
  <div style="display:flex;gap:4px">
    <RChip size="small" prepend-icon="mdi-playlist-music">3 / 70</RChip>
    <RChip size="small" prepend-icon="mdi-account-music">Composer</RChip>
    <RChip size="small" prepend-icon="mdi-calendar" color="accent">2022</RChip>
    <RChip size="small" prepend-icon="mdi-music-clef-treble">Soundtrack</RChip>
    <RChip size="small" prepend-icon="mdi-disc">Disc 1</RChip>
  </div>
`;

export const Overflowing: Story = {
  render: (args) => ({
    components: { RMarquee, RChip },
    setup: () => ({ args }),
    template: `<div style="width:240px"><RMarquee v-bind="args">${chips}</RMarquee></div>`,
  }),
};

export const Fits: Story = {
  render: (args) => ({
    components: { RMarquee, RChip },
    setup: () => ({ args }),
    template: `<div style="width:640px"><RMarquee v-bind="args">${chips}</RMarquee></div>`,
  }),
};
