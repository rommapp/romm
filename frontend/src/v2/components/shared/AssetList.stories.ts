import type { Meta, StoryObj } from "@storybook/vue3-vite";
import { ref } from "vue";
import type { SaveSchema, StateSchema } from "@/__generated__";
import AssetActions from "@/v2/components/GameDetails/AssetActions.vue";
import {
  identicalPrefixStates,
  makeSave,
  makeSaveSlot,
  manyStates,
  saveScreenshot,
  saveSlotLibrary,
  toUserSave,
} from "@/v2/utils/saveStateStoryFixtures";
import AssetList from "./AssetList.vue";

const listDecorator = [
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
];

const meta: Meta<typeof AssetList> = {
  title: "Shared/AssetList",
  component: AssetList,
  decorators: listDecorator,
};

export default meta;
type Story = StoryObj<typeof AssetList>;

function selectableSaves(saves: SaveSchema[], selected: number | null) {
  return {
    components: { AssetList },
    setup() {
      const selectedId = ref<number | null>(selected);
      return {
        saves,
        selectedId,
        onSelect: (a: SaveSchema) => (selectedId.value = a.id),
      };
    },
    template: `
      <AssetList :assets="saves" type="save" :selected-id="selectedId" @select="onSelect" />
    `,
  };
}

function selectableStates(states: StateSchema[], selected: number | null) {
  return {
    components: { AssetList },
    setup() {
      const selectedId = ref<number | null>(selected);
      return {
        states,
        selectedId,
        onSelect: (a: StateSchema) => (selectedId.value = a.id),
      };
    },
    template: `
      <AssetList :assets="states" type="state" :selected-id="selectedId" @select="onSelect" />
    `,
  };
}

export const SlotLibrary: Story = {
  name: "Saves · slots (selectable)",
  render: () => {
    const saves = saveSlotLibrary();
    return selectableSaves(saves, saves[0].id);
  },
};

export const OlderVersionSelected: Story = {
  name: "Saves · older version selected",
  render: () => {
    const saves = saveSlotLibrary();
    const olderMainQuest = saves.filter((s) => s.slot === "main_quest")[3];
    return selectableSaves(saves, olderMainQuest.id);
  },
};

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
    return selectableSaves(saves, null);
  },
};

export const StreamArchives: Story = {
  name: "Saves · stream (created, flat)",
  render: () => {
    const saves = [
      makeSave(1, null, 10, { screenshot: saveScreenshot(120) }),
      makeSave(2, null, 20),
      makeSave(3, null, 30, { screenshot: saveScreenshot(200) }),
    ];
    return {
      components: { AssetList },
      setup() {
        const selectedId = ref<number | null>(saves[0].id);
        return {
          saves,
          selectedId,
          onSelect: (a: SaveSchema) => (selectedId.value = a.id),
        };
      },
      template: `
        <AssetList
          :assets="saves"
          type="save"
          timestamp="created"
          :group-by-slot="false"
          :selected-id="selectedId"
          @select="onSelect"
        />
      `,
    };
  },
};

export const SaveWithContentHash: Story = {
  name: "Saves · content hash (fixture)",
  render: () => {
    const saves = [
      makeSave(1, "main_quest", 2, {
        content_hash: "a1b2c3d4e5f6789012345678901234ab",
      }),
    ];
    return selectableSaves(saves, saves[0].id);
  },
};

export const SingleSave: Story = {
  name: "Saves · single",
  render: () => {
    const saves = makeSaveSlot("autosave", 1, 2, 1);
    return selectableSaves(saves, saves[0].id);
  },
};

export const StatesSelectable: Story = {
  name: "States · selectable",
  render: () => {
    const states = manyStates(5);
    return selectableStates(states, states[0].id);
  },
};

export const IdenticalPrefixStates: Story = {
  name: "States · identical prefix",
  render: () => {
    const states = identicalPrefixStates(4);
    return selectableStates(states, states[0].id);
  },
};

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

export const CommunitySaves: Story = {
  name: "Saves · community (show owner)",
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

export const EmptySaves: Story = {
  name: "Empty · saves",
  render: () => ({
    components: { AssetList },
    template: `
      <AssetList :assets="[]" type="save" :selected-id="null" />
    `,
  }),
};

export const EmptyStates: Story = {
  name: "Empty · states",
  render: () => ({
    components: { AssetList },
    template: `
      <AssetList :assets="[]" type="state" :selected-id="null" />
    `,
  }),
};
