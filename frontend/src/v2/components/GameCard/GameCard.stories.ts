import type { Meta, StoryObj } from "@storybook/vue3-vite";
import type { SimpleRom } from "@/stores/roms";
import { romFixture } from "@/utils/rom.fixtures";
import GameCard from "./GameCard.vue";

const sampleRom = romFixture({
  id: 1,
  name: "Super Mario World",
  fs_name_no_ext: "Super Mario World (USA)",
  platform_display_name: "Super Nintendo",
  platform_custom_name: null,
  platform_slug: "snes",
  path_cover_large: null,
  path_cover_small: null,
  url_cover: null,
  regions: ["US"],
  languages: ["en"],
});

const meta: Meta<typeof GameCard> = {
  title: "Media/GameCard",
  component: GameCard,
  // Rendered as in the gallery: a link card with the multi-select checkbox,
  // so the a11y check covers both.
  args: { selectable: true, position: 0 },
  argTypes: {
    hero: { control: "boolean" },
    focused: { control: "boolean" },
    showPlatformIcon: { control: "boolean" },
  },
};

export default meta;

type Story = StoryObj<typeof GameCard>;

export const Default: Story = {
  render: (args) => ({
    components: { GameCard },
    setup: () => ({ args, rom: sampleRom }),
    template: `<div style="width:180px"><GameCard :rom="rom" v-bind="args" /></div>`,
  }),
};

export const Focused: Story = {
  ...Default,
  args: { focused: true },
};

export const Hero: Story = {
  ...Default,
  args: { hero: true },
};

export const Grid: Story = {
  render: () => ({
    components: { GameCard },
    setup: () => {
      const roms: SimpleRom[] = [
        { ...sampleRom, id: 1, name: "Super Mario World" },
        { ...sampleRom, id: 2, name: "Chrono Trigger" },
        {
          ...sampleRom,
          id: 3,
          name: "Legend of Zelda: A Link to the Past",
        },
        { ...sampleRom, id: 4, name: "Earthbound" },
        { ...sampleRom, id: 5, name: "Super Metroid" },
        { ...sampleRom, id: 6, name: "F-Zero" },
      ];
      return { roms };
    },
    template: `
      <div style="display:grid;grid-template-columns:repeat(3,180px);gap:1.5rem">
        <GameCard v-for="(rom, i) in roms" :key="rom.id" :rom="rom" selectable :position="i" />
      </div>
    `,
  }),
};
