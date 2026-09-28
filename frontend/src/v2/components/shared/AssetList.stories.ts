import type { Meta, StoryObj } from "@storybook/vue3-vite";
import { expect, userEvent, within } from "storybook/test";
import { ref } from "vue";
import AssetActions from "@/v2/components/shared/AssetActions.vue";
import type { Asset, AssetType } from "@/v2/utils/assets";
import {
  IDENTICAL_STATE_PREFIX,
  identicalPrefixStates,
  makeSave,
  makeSaveSlot,
  manyStates,
  saveScreenshot,
  saveSlotLibrary,
  toUserSave,
} from "@/v2/utils/saveStates.fixtures";
import {
  deleteButtons,
  downloadButtons,
  selectableItems,
} from "@/v2/utils/saveStates.plays";
import AssetList from "./AssetList.vue";

const meta: Meta<typeof AssetList> = {
  title: "Shared/AssetList",
  component: AssetList,
  decorators: [
    () => ({
      template: `
        <div style="
          max-width: 520px;
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
type Story = StoryObj<typeof AssetList>;

function selectableList(
  assets: Asset[],
  type: AssetType,
  selected: number | null,
  extra: Partial<InstanceType<typeof AssetList>["$props"]> = {},
) {
  return {
    components: { AssetList },
    setup() {
      const selectedId = ref<number | null>(selected);
      return {
        assets,
        type,
        selectedId,
        extra,
        onSelect: (a: Asset) => (selectedId.value = a.id),
      };
    },
    template: `
      <AssetList
        :assets="assets"
        :type="type"
        :selected-id="selectedId"
        v-bind="extra"
        @select="onSelect"
      />
    `,
  };
}

export const SlotLibrary: Story = {
  name: "Saves · slots (selectable)",
  render: () => {
    const saves = saveSlotLibrary();
    return selectableList(saves, "save", saves[0].id);
  },
  play: async ({ canvasElement, step }) => {
    const ui = within(canvasElement);
    await step("named slot groups are visible", async () => {
      expect(ui.getByText("autosave")).toBeTruthy();
      expect(ui.getByText("main_quest")).toBeTruthy();
    });
    await step("clicking a row updates selection", async () => {
      const target = selectableItems(canvasElement).find(
        (r) => r.getAttribute("aria-pressed") === "false",
      );
      expect(target).toBeTruthy();
      await userEvent.click(target!);
      expect(target).toHaveAttribute("aria-pressed", "true");
    });
  },
};

// Selecting an older version unfolds its slot so the pick stays visible.
export const OlderVersionSelected: Story = {
  name: "Saves · older version selected",
  render: () => {
    const saves = saveSlotLibrary();
    const olderMainQuest = saves.filter((s) => s.slot === "main_quest")[3];
    return selectableList(saves, "save", olderMainQuest.id);
  },
};

// Only manual uploads, no screenshots: the pre-slot shape of a library.
export const ArchiveOnly: Story = {
  name: "Saves · archive only",
  render: () => {
    const saves = [
      makeSave(1, null, 3),
      makeSave(2, null, 50, {
        file_name:
          "the_legend_of_zelda_a_link_to_the_past_speedrun_attempt_27.srm",
      }),
      makeSave(3, null, 400, { emulator: null }),
    ];
    return selectableList(saves, "save", null);
  },
};

// Flat list ordered by upload time, as the player's stream picker shows it.
export const StreamArchives: Story = {
  name: "Saves · stream (created, flat)",
  render: () => {
    const saves = [
      makeSave(1, null, 10, { screenshot: saveScreenshot(120) }),
      makeSave(2, null, 20),
      makeSave(3, null, 30, { screenshot: saveScreenshot(200) }),
    ];
    return selectableList(saves, "save", saves[0].id, {
      timestamp: "created",
      groupBySlot: false,
    });
  },
};

// One slot, one version, the most common case for new players.
export const SingleSave: Story = {
  name: "Saves · single",
  render: () => {
    const saves = makeSaveSlot("autosave", 1, 2, 1);
    return selectableList(saves, "save", saves[0].id);
  },
};

export const StatesSelectable: Story = {
  name: "States · selectable",
  render: () => {
    const states = manyStates(5);
    return selectableList(states, "state", states[0].id);
  },
};

export const IdenticalPrefixStates: Story = {
  name: "States · identical prefix",
  render: () => {
    const states = identicalPrefixStates(4);
    return selectableList(states, "state", states[0].id);
  },
  play: async ({ canvasElement, step }) => {
    await step("each row keeps the full filename in the DOM", async () => {
      const rows = selectableItems(canvasElement);
      expect(rows).toHaveLength(4);
      for (const el of rows) {
        expect(el.textContent).toContain(IDENTICAL_STATE_PREFIX);
      }
    });
  },
};

// Management mode: static rows hosting the actions slot.
export const ManageSaves: Story = {
  name: "Saves · manage + actions",
  render: () => ({
    components: { AssetList, AssetActions },
    setup() {
      return { saves: saveSlotLibrary() };
    },
    template: `
      <AssetList :assets="saves" type="save" :selectable="false" :scrollable="false">
        <template #actions="{ asset }">
          <AssetActions :asset="asset" type="save" own />
        </template>
      </AssetList>
    `,
  }),
  play: async ({ canvasElement, step }) => {
    await step(
      "manage rows are list items, not selectable buttons",
      async () => {
        const ui = within(canvasElement);
        const rows = ui.getAllByRole("listitem");
        expect(
          rows.some((r) => r.textContent?.includes("chrono_trigger")),
        ).toBe(true);
        expect(
          ui.queryAllByRole("button", { name: /^chrono_trigger/ }),
        ).toEqual([]);
      },
    );
    await step("own-item actions include download and delete", async () => {
      expect(downloadButtons(canvasElement).length).toBeGreaterThan(0);
      expect(deleteButtons(canvasElement).length).toBeGreaterThan(0);
    });
  },
};

export const ManageStates: Story = {
  name: "States · manage + actions",
  render: () => ({
    components: { AssetList, AssetActions },
    setup() {
      return { states: identicalPrefixStates(3) };
    },
    template: `
      <AssetList :assets="states" type="state" :selectable="false" :scrollable="false">
        <template #actions="{ asset }">
          <AssetActions :asset="asset" type="state" own />
        </template>
      </AssetList>
    `,
  }),
};

// Other users' public saves show an owner chip and only a download action.
export const CommunitySaves: Story = {
  name: "Saves · community (show owner)",
  play: async ({ canvasElement, step }) => {
    const ui = within(canvasElement);
    await step("community author chips render", async () => {
      expect(ui.getByText("speedrunner42")).toBeTruthy();
      expect(ui.getByText("archivist")).toBeTruthy();
    });
    await step("community rows offer download only", async () => {
      expect(downloadButtons(canvasElement).length).toBe(2);
      expect(ui.queryByRole("button", { name: /^Delete /i })).toBeNull();
    });
  },
  render: () => ({
    components: { AssetList, AssetActions },
    setup() {
      const saves = [
        toUserSave(makeSave(50, "route_a", 12), "speedrunner42", {
          user_id: 2,
        }),
        toUserSave(makeSave(51, "route_b", 24), "archivist", {
          user_id: 3,
        }),
      ];
      return { saves };
    },
    template: `
      <AssetList
        :assets="saves"
        type="save"
        :selectable="false"
        :scrollable="false"
        show-owner
      >
        <template #actions="{ asset }">
          <AssetActions :asset="asset" type="save" />
        </template>
      </AssetList>
    `,
  }),
};

// Empty, distinct from "no save selected".
export const EmptySaves: Story = {
  name: "Empty · saves",
  render: () => ({
    components: { AssetList },
    template: `
      <AssetList :assets="[]" type="save" :selected-id="null" />
    `,
  }),
  play: async ({ canvasElement, step }) => {
    await step("empty saves message", async () => {
      expect(
        within(canvasElement).getByText("No saves available"),
      ).toBeTruthy();
    });
  },
};

export const EmptyStates: Story = {
  name: "Empty · states",
  render: () => ({
    components: { AssetList },
    template: `
      <AssetList :assets="[]" type="state" :selected-id="null" />
    `,
  }),
  play: async ({ canvasElement, step }) => {
    await step("empty states message", async () => {
      expect(
        within(canvasElement).getByText("No states available"),
      ).toBeTruthy();
    });
  },
};
