// AssetStrip is the horizontal card variant used for STATES in most surfaces.
// Saves render through <AssetList> (vertical rows). Stories here cover strip
// layouts plus Save data manage mode (flow + group-by emulator).
import type { Meta, StoryObj } from "@storybook/vue3-vite";
import { expect, userEvent } from "storybook/test";
import { ref } from "vue";
import type { StateSchema } from "@/__generated__";
import AssetActions from "@/v2/components/GameDetails/AssetActions.vue";
import {
  makeState,
  manyStates,
  mixedCommunityStates,
  storyStateScreenshot,
} from "@/v2/utils/saveStateStoryFixtures";
import {
  canvas,
  downloadButtons,
  stripTiles,
} from "@/v2/utils/saveStateStoryPlays";
import AssetStrip from "./AssetStrip.vue";

const stripDecorator = [
  () => ({
    template: `
      <div style="
        max-width: 720px;
        padding: 18px;
        background: var(--r-color-bg-elevated);
        border: 1px solid var(--r-color-border);
        border-radius: var(--r-radius-lg);
      ">
        <story />
      </div>
    `,
  }),
];

const meta: Meta<typeof AssetStrip> = {
  title: "Shared/AssetStrip",
  component: AssetStrip,
  decorators: stripDecorator,
};

export default meta;

type Story = StoryObj<typeof AssetStrip>;

function selectableStrip(
  states: StateSchema[],
  selected: number | null,
  extra: Record<string, unknown> = {},
) {
  return {
    components: { AssetStrip },
    setup() {
      const selectedId = ref<number | null>(selected);
      return {
        states,
        selectedId,
        extra,
        onSelect: (a: StateSchema) => (selectedId.value = a.id),
      };
    },
    template: `
      <AssetStrip
        :assets="states"
        type="state"
        :selected-id="selectedId"
        v-bind="extra"
        @select="onSelect"
      />
    `,
  };
}

export const FewStatesScreenshots: Story = {
  name: "States · 5 with screenshots",
  render: () => {
    const states = manyStates(5);
    return selectableStrip(states, states[0].id);
  },
  play: async ({ canvasElement, step }) => {
    await step("state tiles render with filenames", async () => {
      expect(stripTiles(canvasElement).length).toBe(5);
      expect(canvasElement.textContent).toContain("overworld_1.state");
    });
    await step("clicking a tile selects it", async () => {
      const tiles = stripTiles(canvasElement);
      const target = tiles.find(
        (t) => t.getAttribute("aria-pressed") === "false",
      );
      expect(target).toBeTruthy();
      await userEvent.click(target!);
      expect(target).toHaveAttribute("aria-pressed", "true");
    });
  },
};

export const ManyStatesOverflow: Story = {
  name: "States · 12 (horizontal scroll)",
  render: () => {
    const states = manyStates(12);
    return selectableStrip(states, states[4].id);
  },
};

export const ManyStatesGrid: Story = {
  name: "States · 30 (grid layout)",
  render: () => {
    const states = manyStates(30);
    return selectableStrip(states, states[0].id, { layout: "grid" });
  },
};

export const ManyStatesList: Story = {
  name: "States · 30 (list layout)",
  render: () => {
    const states = manyStates(30);
    return selectableStrip(states, states[0].id, { layout: "list" });
  },
};

export const StatesNoScreenshots: Story = {
  name: "States · 6 without screenshots",
  render: () => {
    const states = manyStates(6, false);
    return selectableStrip(states, states[2].id);
  },
};

export const LongFilenames: Story = {
  name: "Long filenames (ellipsis)",
  render: () => {
    const states = [
      makeState({
        id: 1,
        file_name: "the_legend_of_zelda_a_link_to_the_past_speedrun_27.state",
        screenshot: storyStateScreenshot(
          "https://placehold.co/640x360/2d2147/ffffff?text=LTTP",
          1,
        ),
      }),
      makeState({
        id: 2,
        file_name:
          "chrono_trigger_new_game_plus_attempt_third_run_boss_room.state",
        screenshot: storyStateScreenshot(
          "https://placehold.co/640x360/4a1a1a/ffffff?text=CT+NG%2B",
          2,
        ),
      }),
      makeState({
        id: 3,
        file_name: "super_mario_world_special_world_complete_run.state",
        screenshot: null,
      }),
    ];
    return selectableStrip(states, states[0].id);
  },
};

export const NoneSelected: Story = {
  name: "States · none selected",
  render: () => selectableStrip(manyStates(4), null),
};

export const EmptyStates: Story = {
  name: "Empty (no states)",
  render: () => ({
    components: { AssetStrip },
    template: `
      <AssetStrip :assets="[]" type="state" :selected-id="null" />
    `,
  }),
  play: async ({ canvasElement, step }) => {
    await step("empty states message", async () => {
      expect(
        canvas(canvasElement).getByText("No states available"),
      ).toBeTruthy();
    });
  },
};

export const IncompatibleStates: Story = {
  name: "States · 6, half from another emulator",
  render: () => {
    const states = manyStates(6).map((state, i) => ({
      ...state,
      emulator: i % 2 === 0 ? "snes9x" : "builtin",
    }));
    const disabledReason = (asset: { emulator?: string | null }) =>
      asset.emulator === "snes9x"
        ? null
        : `Saved with ${asset.emulator}, which the selected core cannot load.`;
    return {
      components: { AssetStrip },
      setup() {
        const selectedId = ref<number | null>(states[0].id);
        return {
          states,
          selectedId,
          disabledReason,
          onSelect: (a: StateSchema) => (selectedId.value = a.id),
        };
      },
      template: `
        <AssetStrip
          :assets="states"
          type="state"
          :selected-id="selectedId"
          :disabled-reason="disabledReason"
          @select="onSelect"
        />
      `,
    };
  },
};

export const GroupedByCore: Story = {
  name: "States · grouped by core",
  render: () => {
    const states = manyStates(9).map((state, i) => ({
      ...state,
      emulator: i % 3 === 0 ? "snes9x" : i % 3 === 1 ? "builtin" : null,
    }));
    const disabledReason = (asset: { emulator?: string | null }) =>
      asset.emulator === "builtin"
        ? "Saved with builtin, which the selected core cannot load."
        : null;
    return selectableStrip(states, states[0].id, {
      layout: "flow",
      groupBy: "emulator",
      disabledReason,
    });
  },
};

export const ManageFlowGrouped: Story = {
  name: "Manage · flow + grouped (Save data)",
  render: () => ({
    components: { AssetStrip, AssetActions },
    setup() {
      return { states: manyStates(6) };
    },
    template: `
      <AssetStrip
        :assets="states"
        type="state"
        :selectable="false"
        layout="flow"
        group-by="emulator"
      >
        <template #actions="{ asset }">
          <AssetActions :asset="asset" type="state" own />
        </template>
      </AssetStrip>
    `,
  }),
  play: async ({ canvasElement, step }) => {
    const ui = canvas(canvasElement);
    await step("core group headings appear", async () => {
      expect(ui.getByRole("button", { name: /snes9x/i })).toBeTruthy();
    });
    await step("static tiles host per-item actions", async () => {
      const staticTiles = canvasElement.querySelectorAll(
        ".r-asset-strip__tile--static",
      );
      expect(staticTiles.length).toBeGreaterThan(0);
      expect(downloadButtons(canvasElement).length).toBeGreaterThan(0);
    });
  },
};

export const ManageCommunity: Story = {
  name: "Manage · community + show owner",
  render: () => ({
    components: { AssetStrip, AssetActions },
    setup() {
      const states = mixedCommunityStates().filter((s) => s.user_id !== 1);
      return { states };
    },
    template: `
      <AssetStrip
        :assets="states"
        type="state"
        :selectable="false"
        layout="flow"
        group-by="emulator"
        show-owner
      >
        <template #actions="{ asset }">
          <AssetActions :asset="asset" type="state" />
        </template>
      </AssetStrip>
    `,
  }),
};
