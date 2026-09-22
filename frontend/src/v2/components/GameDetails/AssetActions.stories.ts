import type { Meta, StoryObj } from "@storybook/vue3-vite";
import { expect } from "storybook/test";
import { makeSave, makeState } from "@/v2/utils/saveStateStoryFixtures";
import { canvas } from "@/v2/utils/saveStateStoryPlays";
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
  play: async ({ canvasElement, step }) => {
    const ui = canvas(canvasElement);
    await step("public save shows make-private control", async () => {
      expect(ui.getByRole("button", { name: "Make Private" })).toBeTruthy();
      expect(ui.getByRole("button", { name: /^Download /i })).toBeTruthy();
      expect(ui.getByRole("button", { name: /^Delete /i })).toBeTruthy();
    });
  },
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
  play: async ({ canvasElement, step }) => {
    await step("private save shows make-public control", async () => {
      expect(
        canvas(canvasElement).getByRole("button", { name: "Make Public" }),
      ).toBeTruthy();
    });
  },
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
  play: async ({ canvasElement, step }) => {
    const ui = canvas(canvasElement);
    await step("community item is download-only", async () => {
      expect(ui.getByRole("button", { name: /^Download /i })).toBeTruthy();
      expect(ui.queryByRole("button", { name: /^Delete /i })).toBeNull();
      expect(ui.queryByRole("button", { name: "Make Private" })).toBeNull();
    });
  },
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
