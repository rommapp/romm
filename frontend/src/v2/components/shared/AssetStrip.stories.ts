// AssetStrip is the card variant for states; saves render through <AssetList>.
import type { Meta, StoryObj } from "@storybook/vue3-vite";
import { expect, userEvent, within } from "storybook/test";
import { ref } from "vue";
import type { StateSchema } from "@/__generated__";
import AssetActions from "@/v2/components/shared/AssetActions.vue";
import {
  makeState,
  manyStates,
  mixedCommunityStates,
  screenshotFixture,
} from "@/v2/utils/saveStates.fixtures";
import { downloadButtons, selectableItems } from "@/v2/utils/saveStates.plays";
import AssetStrip from "./AssetStrip.vue";

const meta: Meta<typeof AssetStrip> = {
  title: "Shared/AssetStrip",
  component: AssetStrip,
  decorators: [
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
  ],
};

export default meta;

type Story = StoryObj<typeof AssetStrip>;

function selectableStrip(
  states: StateSchema[],
  selected: number | null,
  extra: Partial<InstanceType<typeof AssetStrip>["$props"]> = {},
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

// Five states with screenshots, the headline case. The selected tile
// carries the brand ring and check badge.
export const FewStatesScreenshots: Story = {
  name: "States · 5 with screenshots",
  render: () => {
    const states = manyStates(5);
    return selectableStrip(states, states[0]!.id);
  },
  play: async ({ canvasElement, step }) => {
    await step("state tiles render with filenames", async () => {
      await expect(selectableItems(canvasElement).length).toBe(5);
      await expect(canvasElement.textContent).toContain("overworld_1.state");
    });
    await step("clicking a tile selects it", async () => {
      const tiles = selectableItems(canvasElement);
      const target = tiles.find(
        (t) => t.getAttribute("aria-pressed") === "false",
      );
      await expect(target).toBeTruthy();
      await userEvent.click(target!);
      await expect(target).toHaveAttribute("aria-pressed", "true");
    });
  },
};

// Twelve states overflow; tiles scroll horizontally with snap.
export const ManyStatesOverflow: Story = {
  name: "States · 12 (horizontal scroll)",
  render: () => {
    const states = manyStates(12);
    return selectableStrip(states, states[4]!.id);
  },
};

// Grid and list: a long history, where the horizontal strip buries the
// older entries behind a scroll.
export const ManyStatesGrid: Story = {
  name: "States · 30 (grid layout)",
  render: () => {
    const states = manyStates(30);
    return selectableStrip(states, states[0]!.id, { layout: "grid" });
  },
};

export const ManyStatesList: Story = {
  name: "States · 30 (list layout)",
  render: () => {
    const states = manyStates(30);
    return selectableStrip(states, states[0]!.id, { layout: "list" });
  },
};

// States without a screenshot fall back to a gradient with the file icon.
export const StatesNoScreenshots: Story = {
  name: "States · 6 without screenshots",
  render: () => {
    const states = manyStates(6).map((s) => ({ ...s, screenshot: null }));
    return selectableStrip(states, states[2]!.id);
  },
};

// Long filenames should ellipsis cleanly without breaking the row.
export const LongFilenames: Story = {
  name: "Long filenames (ellipsis)",
  render: () => {
    const states = [
      makeState({
        id: 1,
        file_name: "the_legend_of_zelda_a_link_to_the_past_speedrun_27.state",
        screenshot: screenshotFixture(
          "https://placehold.co/640x360/2d2147/ffffff?text=LTTP",
          1,
        ),
      }),
      makeState({
        id: 2,
        file_name:
          "chrono_trigger_new_game_plus_attempt_third_run_boss_room.state",
        screenshot: screenshotFixture(
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
    return selectableStrip(states, states[0]!.id);
  },
};

// Nothing selected yet; the strip is still clickable.
export const NoneSelected: Story = {
  name: "States · none selected",
  render: () => selectableStrip(manyStates(4), null),
};

// Empty, distinct from "no asset selected".
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
      await expect(
        within(canvasElement).getByText("No states available"),
      ).toBeTruthy();
    });
  },
};

// States from another emulator stay listed, dimmed, but cannot be picked.
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
    return selectableStrip(states, states[0]!.id, { disabledReason });
  },
};

// One collapsible mini grid per core. The core that cannot load starts
// closed and its tiles are greyed out when opened.
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
    return selectableStrip(states, states[0]!.id, {
      layout: "flow",
      groupBy: "emulator",
      disabledReason,
    });
  },
};

// Save data management: static tiles grouped by core, hosting the actions slot.
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
    const ui = within(canvasElement);
    await step("core group headings appear", async () => {
      await expect(ui.getByRole("button", { name: /snes9x/i })).toBeTruthy();
    });
    await step("static tiles host per-item actions", async () => {
      const staticTiles = within(canvasElement).getAllByRole("listitem");
      await expect(staticTiles.length).toBeGreaterThan(0);
      await expect(downloadButtons(canvasElement).length).toBeGreaterThan(0);
    });
  },
};

// Other users' public states show an owner chip and only a download action.
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
