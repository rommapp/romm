import type { Meta, StoryObj } from "@storybook/vue3-vite";
import { expect, waitFor } from "storybook/test";
import { onMounted } from "vue";
import { useRouter } from "vue-router";
import type { DetailedRomSchema } from "@/__generated__";
import storeAuth from "@/stores/auth";
import {
  mixedCommunitySaves,
  mixedCommunityStates,
  storyAuthUser,
  storyDetailedRom,
} from "@/v2/utils/saveStateStoryFixtures";
import {
  canvas,
  downloadButtons,
  pickSaveDataSubtab,
} from "@/v2/utils/saveStateStoryPlays";
import SaveDataTab from "./SaveDataTab.vue";

type Subtab = "saves" | "states";

interface StoryArgs {
  subtab: Subtab;
  rom: DetailedRomSchema;
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
  decorators: [
    (_, { args }) => ({
      components: { SaveDataTab },
      setup() {
        const router = useRouter();
        onMounted(() => {
          storeAuth().setCurrentUser(storyAuthUser());
          void router.replace({
            query: { tab: "save-data", subtab: args.subtab },
          });
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
  ],
};

export default meta;
type Story = StoryObj<StoryArgs>;

export const SavesFull: Story = {
  name: "Saves · mine + community",
  args: { subtab: "saves", rom: storyDetailedRom() },
  play: async ({ canvasElement, step }) => {
    const ui = canvas(canvasElement);
    await step("saves subtab shows mine and community sections", async () => {
      await waitFor(() => {
        expect(ui.getByText("My saves")).toBeTruthy();
      });
      expect(ui.getAllByText("Community").length).toBeGreaterThanOrEqual(1);
      expect(downloadButtons(canvasElement).length).toBeGreaterThan(0);
    });
    await step("switching to states subtab", async () => {
      await pickSaveDataSubtab(canvasElement, /^States/i);
      await waitFor(() => {
        expect(ui.getByText("My states")).toBeTruthy();
      });
    });
  },
};

export const StatesFull: Story = {
  name: "States · mine + community",
  args: { subtab: "states", rom: storyDetailedRom() },
  play: async ({ canvasElement, step }) => {
    await step("states subtab lists mine section", async () => {
      await waitFor(() => {
        expect(canvas(canvasElement).getByText("My states")).toBeTruthy();
      });
    });
  },
};

export const SavesEmptyMine: Story = {
  name: "Saves · empty mine",
  args: {
    subtab: "saves",
    rom: storyDetailedRom({
      all_user_saves: mixedCommunitySaves().filter((s) => s.user_id !== 1),
    }),
  },
  play: async ({ canvasElement, step }) => {
    await step("empty mine promotes upload dropzone", async () => {
      await waitFor(() => {
        expect(canvas(canvasElement).getByText("No saves yet")).toBeTruthy();
      });
    });
  },
};

export const StatesEmptyMine: Story = {
  name: "States · empty mine",
  args: {
    subtab: "states",
    rom: storyDetailedRom({
      all_user_states: mixedCommunityStates().filter((s) => s.user_id !== 1),
    }),
  },
};

export const SavesMineOnly: Story = {
  name: "Saves · mine only (no community)",
  args: {
    subtab: "saves",
    rom: storyDetailedRom({
      all_user_saves: mixedCommunitySaves().filter((s) => s.user_id === 1),
    }),
  },
};

export const StatesMineOnly: Story = {
  name: "States · mine only",
  args: {
    subtab: "states",
    rom: storyDetailedRom({
      all_user_states: mixedCommunityStates().filter((s) => s.user_id === 1),
    }),
  },
};

export const CompletelyEmpty: Story = {
  name: "Empty · no saves or states",
  args: {
    subtab: "saves",
    rom: storyDetailedRom({ all_user_saves: [], all_user_states: [] }),
  },
};

export const SingleCommunitySave: Story = {
  name: "Saves · community only",
  args: {
    subtab: "saves",
    rom: storyDetailedRom({
      all_user_saves: mixedCommunitySaves().filter((s) => s.user_id !== 1),
    }),
  },
};

export const SingleCommunityState: Story = {
  name: "States · community only",
  args: {
    subtab: "states",
    rom: storyDetailedRom({
      all_user_states: mixedCommunityStates().filter((s) => s.user_id !== 1),
    }),
  },
};
