import type { Meta, StoryObj } from "@storybook/vue3-vite";
import { ref } from "vue";
import type { SaveSchema } from "@/__generated__";
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
    // Every third save is slot-less (mirrors web-player saves, which never
    // carry a slot); the rest are named client slots so the slot chip shows.
    slot: i % 3 === 0 ? null : slot,
    screenshot: null,
    ...overrides,
  } as SaveSchema;
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
