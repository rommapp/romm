import type { Meta, StoryObj } from "@storybook/vue3-vite";
import { expect, waitFor, within } from "storybook/test";
import { useRouter } from "vue-router";
import type { DetailedRomSchema } from "@/__generated__";
import storeAuth from "@/stores/auth";
import { userFixture } from "@/utils/user.fixtures";
import {
  mixedCommunitySaves,
  mixedCommunityStates,
  storyDetailedRom,
} from "@/v2/utils/saveStates.fixtures";
import {
  downloadButtons,
  pickSaveDataSubtab,
} from "@/v2/utils/saveStates.plays";
import SaveDataTab from "./SaveDataTab.vue";

type Subtab = "saves" | "states";

interface StoryArgs {
  subtab: Subtab;
  rom: DetailedRomSchema;
}

const MY_USER_ID = userFixture().id;
const mine = <T extends { user_id: number }>(xs: T[]) =>
  xs.filter((x) => x.user_id === MY_USER_ID);
const theirs = <T extends { user_id: number }>(xs: T[]) =>
  xs.filter((x) => x.user_id !== MY_USER_ID);

const MINE_HEADING: Record<Subtab, string> = {
  saves: "My saves",
  states: "My states",
};

// Both panels stay mounted behind v-show, so only the role query, which skips
// hidden nodes, tells which subtab is on screen.
async function waitForSubtab(root: HTMLElement, subtab: Subtab) {
  await waitFor(() => {
    expect(
      within(root).getByRole("heading", { name: MINE_HEADING[subtab] }),
    ).toBeTruthy();
  });
}

const meta: Meta<StoryArgs> = {
  title: "GameDetails/SaveDataTab",
  component: SaveDataTab,
  parameters: {
    layout: "fullscreen",
  },
  args: {
    subtab: "saves",
    rom: storyDetailedRom(),
  },
  render: (args) => ({
    components: { SaveDataTab },
    setup() {
      storeAuth().setCurrentUser(userFixture({ username: "player" }));
      void useRouter().replace({
        query: { tab: "save-data", subtab: args.subtab },
      });
      return { rom: args.rom };
    },
    template: `
      <div style="
        box-sizing: border-box;
        width: 100%;
        min-height: 100%;
        padding: var(--r-space-4);
        background: var(--r-color-bg);
      ">
        <SaveDataTab :rom="rom" style="height: min(720px, 85vh);" />
      </div>
    `,
  }),
  // Navigation is async, so every story waits for the subtab before the a11y scan.
  play: async ({ canvasElement, args }) => {
    await waitForSubtab(canvasElement, args.subtab);
  },
};

export default meta;
type Story = StoryObj<StoryArgs>;

export const SavesFull: Story = {
  name: "Saves · mine + community",
  play: async ({ canvasElement, step }) => {
    const ui = within(canvasElement);
    await step("saves subtab shows mine and community sections", async () => {
      await waitForSubtab(canvasElement, "saves");
      expect(ui.getByRole("heading", { name: "Community" })).toBeTruthy();
      expect(downloadButtons(canvasElement).length).toBeGreaterThan(0);
    });
    await step("switching to states subtab", async () => {
      await pickSaveDataSubtab(canvasElement, /^States/i);
      await waitForSubtab(canvasElement, "states");
      expect(ui.queryByRole("heading", { name: "My saves" })).toBeNull();
    });
  },
};

export const StatesFull: Story = {
  name: "States · mine + community",
  args: { subtab: "states" },
};

export const SavesEmptyMine: Story = {
  name: "Saves · empty mine",
  args: {
    rom: storyDetailedRom({
      all_user_saves: theirs(mixedCommunitySaves()),
    }),
  },
  play: async ({ canvasElement, step }) => {
    await step("empty mine promotes upload dropzone", async () => {
      await waitForSubtab(canvasElement, "saves");
      expect(within(canvasElement).getByText("No saves yet")).toBeTruthy();
    });
  },
};

export const StatesEmptyMine: Story = {
  name: "States · empty mine",
  args: {
    subtab: "states",
    rom: storyDetailedRom({
      all_user_states: theirs(mixedCommunityStates()),
    }),
  },
};

export const SavesMineOnly: Story = {
  name: "Saves · mine only (no community)",
  args: {
    rom: storyDetailedRom({
      all_user_saves: mine(mixedCommunitySaves()),
    }),
  },
};

export const StatesMineOnly: Story = {
  name: "States · mine only",
  args: {
    subtab: "states",
    rom: storyDetailedRom({
      all_user_states: mine(mixedCommunityStates()),
    }),
  },
};

export const CompletelyEmpty: Story = {
  name: "Empty · no saves or states",
  args: {
    rom: storyDetailedRom({ all_user_saves: [], all_user_states: [] }),
  },
};

export const SingleCommunitySave: Story = {
  name: "Saves · single community save",
  args: {
    rom: storyDetailedRom({
      all_user_saves: theirs(mixedCommunitySaves()).slice(0, 1),
    }),
  },
};

export const SingleCommunityState: Story = {
  name: "States · single community state",
  args: {
    subtab: "states",
    rom: storyDetailedRom({
      all_user_states: theirs(mixedCommunityStates()).slice(0, 1),
    }),
  },
};
