import type { Meta, StoryObj } from "@storybook/vue3-vite";
import { ref } from "vue";
import type { SaveSchema, StateSchema } from "@/__generated__";
import AssetList from "./AssetList.vue";

// ── Mock builders ────────────────────────────────────────────────

const slots = [
  "main_quest",
  "side_quest",
  "speedrun_attempt",
  "boss_rush",
  "casual_run",
  "challenge_mode",
  "ng_plus",
  "completionist",
  "any_percent",
  "post_credits",
];

function makeSave(i: number, overrides: Partial<SaveSchema> = {}): SaveSchema {
  const now = new Date("2026-05-25T20:00:00Z").getTime();
  const slot = slots[i % slots.length];
  return {
    id: i + 1,
    rom_id: 1,
    user_id: 1,
    file_name: `${slot}.srm`,
    file_name_no_tags: `${slot}.srm`,
    file_name_no_ext: slot,
    file_extension: "srm",
    file_path: "/saves/snes",
    file_size_bytes: 4 * 1024 + i * 3 * 1024,
    full_path: `/saves/snes/${slot}.srm`,
    download_path: `/api/saves/${i + 1}/content`,
    missing_from_fs: false,
    created_at: new Date(now - (i + 2) * 86400 * 1000).toISOString(),
    updated_at: new Date(now - (i + 1) * 4 * 3600 * 1000).toISOString(),
    emulator: i % 2 === 0 ? "snes9x" : null,
    slot: i % 3 === 0 ? null : slot, // Every third save is slot-less
    screenshot: null,
    ...overrides,
  } as SaveSchema;
}

// Distinct placeholder shots so a list is scannable at a glance.
const shots = [
  { color: "2d2147", label: "Overworld" },
  { color: "1a3d2e", label: "Forest" },
  { color: "4a1a1a", label: "Boss+Fight" },
  { color: "0a3a5a", label: "Cave" },
];

function screenshot(i: number): StateSchema["screenshot"] {
  const shot = shots[i % shots.length];
  return {
    id: i + 1,
    file_name: `state_${i + 1}.png`,
    download_path: `https://placehold.co/640x360/${shot.color}/ffffff?text=${shot.label}`,
  } as StateSchema["screenshot"];
}

// EmulatorJS names every capture `<rom name> [<stamp>].state`, so the part that
// tells two states apart is the tail the row has to keep reachable.
function makeState(
  i: number,
  overrides: Partial<StateSchema> = {},
): StateSchema {
  const now = new Date("2026-05-25T20:00:00Z").getTime();
  const stamp = new Date(now - (i + 1) * 3 * 3600 * 1000);
  const name = `Super Mario World [${stamp
    .toISOString()
    .replace(/[:.]/g, "-")
    .replace("T", " ")
    .replace("Z", "")}]`;
  return {
    id: i + 1,
    rom_id: 1,
    user_id: 1,
    file_name: `${name}.state`,
    file_name_no_ext: name,
    file_extension: "state",
    file_path: "/states/snes",
    file_size_bytes: 256 * 1024 + i * 73 * 1024,
    full_path: `/states/snes/${name}.state`,
    download_path: `/api/states/${i + 1}/content`,
    missing_from_fs: false,
    created_at: stamp.toISOString(),
    updated_at: stamp.toISOString(),
    emulator: i % 3 === 2 ? null : "snes9x",
    screenshot: screenshot(i),
    ...overrides,
  } as StateSchema;
}

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

// ── Stories ──────────────────────────────────────────────────────

// A handful of saves — classic JRPG-style slot picker.
export const FewSaves: Story = {
  name: "Saves · 4 slots",
  render: () => ({
    components: { AssetList },
    setup() {
      const saves = Array.from({ length: 4 }).map((_, i) => makeSave(i));
      const selectedId = ref<number | null>(saves[1].id);
      return {
        saves,
        selectedId,
        onSelect: (a: SaveSchema) => (selectedId.value = a.id),
      };
    },
    template: `
      <AssetList :assets="saves" type="save" :selected-id="selectedId" @select="onSelect" />
    `,
  }),
};

// Many saves — vertical scroll inside max-height.
export const ManySaves: Story = {
  name: "Saves · 10 (vertical scroll)",
  render: () => ({
    components: { AssetList },
    setup() {
      const saves = Array.from({ length: 10 }).map((_, i) => makeSave(i));
      const selectedId = ref<number | null>(saves[3].id);
      return {
        saves,
        selectedId,
        onSelect: (a: SaveSchema) => (selectedId.value = a.id),
      };
    },
    template: `
      <AssetList :assets="saves" type="save" :selected-id="selectedId" @select="onSelect" />
    `,
  }),
};

// Long filenames — exercise the ellipsis. The exact timestamp on the
// right keeps the layout tidy.
export const LongFilenames: Story = {
  name: "Long filenames",
  render: () => ({
    components: { AssetList },
    setup() {
      const saves: SaveSchema[] = [
        makeSave(0, {
          file_name:
            "the_legend_of_zelda_a_link_to_the_past_speedrun_attempt_27.srm",
        }),
        makeSave(1, {
          file_name:
            "chrono_trigger_new_game_plus_attempt_third_run_boss_room.srm",
        }),
        makeSave(2, {
          file_name: "super_mario_world_special_world_complete_run.srm",
        }),
      ];
      const selectedId = ref<number | null>(saves[0].id);
      return {
        saves,
        selectedId,
        onSelect: (a: SaveSchema) => (selectedId.value = a.id),
      };
    },
    template: `
      <AssetList :assets="saves" type="save" :selected-id="selectedId" @select="onSelect" />
    `,
  }),
};

// One save — most common case for new players.
export const SingleSave: Story = {
  name: "Single save",
  render: () => ({
    components: { AssetList },
    setup() {
      const save = makeSave(0);
      const selectedId = ref<number | null>(save.id);
      return {
        saves: [save],
        selectedId,
        onSelect: (a: SaveSchema) => (selectedId.value = a.id),
      };
    },
    template: `
      <AssetList :assets="saves" type="save" :selected-id="selectedId" @select="onSelect" />
    `,
  }),
};

// None selected — the list is browsable even when nothing's picked.
export const NoneSelected: Story = {
  name: "None selected",
  render: () => ({
    components: { AssetList },
    setup() {
      const saves = Array.from({ length: 4 }).map((_, i) => makeSave(i));
      const selectedId = ref<number | null>(null);
      return {
        saves,
        selectedId,
        onSelect: (a: SaveSchema) => (selectedId.value = a.id),
      };
    },
    template: `
      <AssetList :assets="saves" type="save" :selected-id="selectedId" @select="onSelect" />
    `,
  }),
};

// Empty — distinct from "no save selected".
export const Empty: Story = {
  name: "Empty (no saves)",
  render: () => ({
    components: { AssetList },
    template: `
      <AssetList :assets="[]" type="save" :selected-id="null" />
    `,
  }),
};

// ── States (issue #4320) ─────────────────────────────────────────

// States render through the same list as saves. The capture goes in the
// leading cell, widened to 16:9 so it's actually readable.
export const StatesWithScreenshots: Story = {
  name: "States · 4 with screenshots",
  render: () => ({
    components: { AssetList },
    setup() {
      const states = Array.from({ length: 4 }).map((_, i) => makeState(i));
      const selectedId = ref<number | null>(states[0].id);
      return {
        states,
        selectedId,
        onSelect: (a: StateSchema) => (selectedId.value = a.id),
      };
    },
    template: `
      <AssetList :assets="states" type="state" :selected-id="selectedId" @select="onSelect" />
    `,
  }),
};

// Nothing in the list has a capture, so the leading cell stays the icon
// square it has always been.
export const StatesNoScreenshots: Story = {
  name: "States · none captured",
  render: () => ({
    components: { AssetList },
    setup() {
      const states = Array.from({ length: 3 }).map((_, i) =>
        makeState(i, { screenshot: null }),
      );
      return { states };
    },
    template: `
      <AssetList :assets="states" type="state" :selected-id="null" />
    `,
  }),
};

// One capture missing from an otherwise shot-carrying list: every row keeps
// the wide cell so the filenames stay in one column.
export const StatesMixed: Story = {
  name: "States · one capture missing",
  render: () => ({
    components: { AssetList },
    setup() {
      const states = [
        makeState(0),
        makeState(1, { screenshot: null }),
        makeState(2),
      ];
      return { states };
    },
    template: `
      <AssetList :assets="states" type="state" :selected-id="null" />
    `,
  }),
};

// The Save data tab: static rows with the action buttons in the trailing
// slot. The third state has no emulator, so its chip is absent, not empty.
export const ManageMode: Story = {
  name: "Manage mode (Save data tab)",
  render: () => ({
    components: { AssetList },
    setup() {
      const states = Array.from({ length: 3 }).map((_, i) => makeState(i));
      return { states };
    },
    template: `
      <AssetList :assets="states" type="state" :selectable="false" :scrollable="false">
        <template #actions>
          <button type="button" aria-label="Download">⭳</button>
          <button type="button" aria-label="Delete">✕</button>
        </template>
      </AssetList>
    `,
  }),
};

// ── Save detail (issue #4320) ────────────────────────────────────

// The content hash companion apps compare, on the rows that carry one. The
// third save predates the backfill, so its chip is absent rather than empty.
export const SaveWithDetail: Story = {
  name: "Save · content hashes",
  render: () => ({
    components: { AssetList },
    setup() {
      const saves = [
        makeSave(0, { content_hash: "0123456789abcdef0123456789abcdef" }),
        makeSave(1, { content_hash: "fedcba9876543210fedcba9876543210" }),
        makeSave(2),
      ];
      return { saves };
    },
    template: `
      <AssetList :assets="saves" type="save" :selectable="false" :scrollable="false">
        <template #actions>
          <button type="button" aria-label="Download">⭳</button>
        </template>
      </AssetList>
    `,
  }),
};

// The player attaches one captured frame to the state AND the save, so a
// save list can carry thumbnails too.
export const SavesWithScreenshots: Story = {
  name: "Saves · captured by the player",
  render: () => ({
    components: { AssetList },
    setup() {
      const saves = Array.from({ length: 3 }).map((_, i) =>
        makeSave(i, { screenshot: screenshot(i) as SaveSchema["screenshot"] }),
      );
      return { saves };
    },
    template: `
      <AssetList :assets="saves" type="save" :selected-id="null" />
    `,
  }),
};
