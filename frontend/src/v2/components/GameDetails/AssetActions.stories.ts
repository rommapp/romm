import type { Meta, StoryObj } from "@storybook/vue3-vite";
import { makeSave, makeState } from "@/v2/utils/saveStateStoryFixtures";
import AssetActions from "./AssetActions.vue";

const meta: Meta<typeof AssetActions> = {
  title: "GameDetails/AssetActions",
  component: AssetActions,
  decorators: [
    () => ({
      template: `
        <div style="
          display: flex;
          gap: 4px;
          padding: 16px;
          background: var(--r-color-bg-elevated);
        ">
          <story />
        </div>
      `,
    }),
  ],
};

export default meta;
type Story = StoryObj<typeof AssetActions>;

export const OwnPublic: Story = {
  name: "Own · public",
  render: () => ({
    components: { AssetActions },
    setup() {
      return {
        asset: { ...makeSave(1, "autosave", 1), is_public: true },
      };
    },
    template: `
      <AssetActions :asset="asset" type="save" own />
    `,
  }),
};

export const OwnPrivate: Story = {
  name: "Own · private",
  render: () => ({
    components: { AssetActions },
    setup() {
      return {
        asset: { ...makeSave(2, "main_quest", 2), is_public: false },
      };
    },
    template: `
      <AssetActions :asset="asset" type="save" own />
    `,
  }),
};

export const OwnToggling: Story = {
  name: "Own · toggling",
  render: () => ({
    components: { AssetActions },
    setup() {
      return {
        asset: { ...makeSave(3, "speedrun", 3), is_public: true },
      };
    },
    template: `
      <AssetActions :asset="asset" type="state" own toggling />
    `,
  }),
};

export const Community: Story = {
  name: "Community · download only",
  render: () => ({
    components: { AssetActions },
    setup() {
      return { asset: makeState({ id: 4 }) };
    },
    template: `
      <AssetActions :asset="asset" type="state" />
    `,
  }),
};
