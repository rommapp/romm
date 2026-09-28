import type { Meta, StoryObj } from "@storybook/vue3-vite";
import { makeSave, makeState } from "@/v2/utils/saveStates.fixtures";
import AssetActions from "./AssetActions.vue";

// Which buttons render for each case is covered by AssetActions.test.ts.
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

export const OwnSave: Story = {
  name: "Own · save",
  args: { asset: makeSave(1, "autosave", 1), type: "save", own: true },
};

export const OwnFavoriteState: Story = {
  name: "Own · favorite state",
  args: {
    asset: makeState({ id: 2, is_favorite: true }),
    type: "state",
    own: true,
  },
};

export const OwnFavoriting: Story = {
  name: "Own · favoriting",
  args: {
    asset: makeSave(3, "speedrun", 3),
    type: "save",
    own: true,
    favoriting: true,
  },
};

export const Community: Story = {
  name: "Community · download only",
  args: { asset: makeState({ id: 4 }), type: "state" },
};
