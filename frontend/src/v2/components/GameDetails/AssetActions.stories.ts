import type { Meta, StoryObj } from "@storybook/vue3-vite";
import { expect, within } from "storybook/test";
import { makeSave, makeState } from "@/v2/utils/saveStates.fixtures";
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

export const OwnSave: Story = {
  name: "Own · save",
  render: () => ({
    components: { AssetActions },
    setup() {
      return { asset: makeSave(1, "autosave", 1) };
    },
    template: `<AssetActions :asset="asset" type="save" own />`,
  }),
  play: async ({ canvasElement, step }) => {
    const ui = within(canvasElement);
    await step(
      "own save gets download, edit, favorite and delete",
      async () => {
        expect(ui.getByRole("button", { name: /^Download /i })).toBeTruthy();
        expect(ui.getByRole("button", { name: "Edit save" })).toBeTruthy();
        expect(
          ui.getByRole("button", { name: "Add to favorites" }),
        ).toHaveAttribute("aria-pressed", "false");
        expect(ui.getByRole("button", { name: "Delete save" })).toBeTruthy();
      },
    );
  },
};

export const OwnFavoriteState: Story = {
  name: "Own · favorite state",
  render: () => ({
    components: { AssetActions },
    setup() {
      return { asset: makeState({ id: 2, is_favorite: true }) };
    },
    template: `<AssetActions :asset="asset" type="state" own />`,
  }),
  play: async ({ canvasElement, step }) => {
    const ui = within(canvasElement);
    await step("favorite state offers to remove it", async () => {
      expect(
        ui.getByRole("button", { name: "Remove from favorites" }),
      ).toHaveAttribute("aria-pressed", "true");
      expect(ui.getByRole("button", { name: "Edit state" })).toBeTruthy();
      expect(ui.getByRole("button", { name: "Delete state" })).toBeTruthy();
    });
  },
};

export const OwnFavoriting: Story = {
  name: "Own · favoriting",
  render: () => ({
    components: { AssetActions },
    setup() {
      return { asset: makeSave(3, "speedrun", 3) };
    },
    template: `<AssetActions :asset="asset" type="save" own favoriting />`,
  }),
};

export const Community: Story = {
  name: "Community · download only",
  render: () => ({
    components: { AssetActions },
    setup() {
      return { asset: makeState({ id: 4 }) };
    },
    template: `<AssetActions :asset="asset" type="state" />`,
  }),
  play: async ({ canvasElement, step }) => {
    const ui = within(canvasElement);
    await step("community item is download-only", async () => {
      expect(ui.getByRole("button", { name: /^Download /i })).toBeTruthy();
      expect(ui.queryByRole("button", { name: /^Edit /i })).toBeNull();
      expect(ui.queryByRole("button", { name: /favorites$/i })).toBeNull();
      expect(ui.queryByRole("button", { name: /^Delete /i })).toBeNull();
    });
  },
};
