// AssetStrip is the horizontal card variant used for STATES only —
// saves render through <AssetList> (vertical rows). Stories here are
// state-focused; see AssetList.stories.ts for the save scenarios.
import type { Meta, StoryObj } from "@storybook/vue3-vite";
import { ref } from "vue";
import type { StateSchema } from "@/__generated__";
import AssetStrip from "./AssetStrip.vue";

// ── Mock builders ────────────────────────────────────────────────

function makeState(overrides: Partial<StateSchema> = {}): StateSchema {
  const base = {
    id: 1,
    rom_id: 1,
    user_id: 1,
    file_name: "state_1.state",
    file_name_no_tags: "state_1.state",
    file_name_no_ext: "state_1",
    file_extension: "state",
    file_path: "/states/snes",
    file_size_bytes: 524288,
    full_path: "/states/snes/state_1.state",
    download_path: "/api/states/1/content",
    missing_from_fs: false,
    created_at: "2026-04-02T09:00:00Z",
    updated_at: "2026-05-13T22:08:00Z",
    emulator: "snes9x",
    screenshot: {
      id: 1,
      rom_id: 1,
      user_id: 1,
      file_name: "state_1.png",
      file_name_no_tags: "state_1.png",
      file_name_no_ext: "state_1",
      file_extension: "png",
      file_path: "/screenshots/snes",
      download_path:
        "https://placehold.co/640x360/2d2147/ffffff?text=Save+State",
    } as StateSchema["screenshot"],
  };
  return { ...base, ...overrides } as StateSchema;
}

// Distinct placeholder shots so we can scan the strip visually.
const shots: { color: string; label: string }[] = [
  { color: "2d2147", label: "Overworld" },
  { color: "1a3d2e", label: "Forest" },
  { color: "4a1a1a", label: "Boss+Fight" },
  { color: "0a3a5a", label: "Cave" },
  { color: "5a3a0a", label: "Desert" },
  { color: "3a0a4a", label: "Castle" },
  { color: "0a5a3a", label: "Lake" },
  { color: "5a0a3a", label: "Volcano" },
  { color: "1a1a5a", label: "Sky" },
  { color: "5a5a0a", label: "Tower" },
];

function manyStates(n: number, withScreenshots = true): StateSchema[] {
  const now = new Date("2026-05-25T20:00:00Z").getTime();
  const deltas = [
    2 * 3600,
    5 * 3600,
    24 * 3600,
    2 * 86400,
    4 * 86400,
    7 * 86400,
    14 * 86400,
    30 * 86400,
    60 * 86400,
    180 * 86400,
  ];
  return Array.from({ length: n }).map((_, i) => {
    const shot = shots[i % shots.length];
    return makeState({
      id: i + 1,
      file_name: `${shot.label.replace("+", " ").toLowerCase()}_${i + 1}.state`,
      file_size_bytes: 256 * 1024 + i * 73 * 1024,
      updated_at: new Date(
        now - deltas[i % deltas.length] * 1000,
      ).toISOString(),
      screenshot: withScreenshots
        ? ({
            ...(makeState().screenshot as NonNullable<
              StateSchema["screenshot"]
            >),
            download_path: `https://placehold.co/640x360/${shot.color}/ffffff?text=${shot.label}`,
          } as StateSchema["screenshot"])
        : null,
      emulator: i % 3 === 0 ? "snes9x" : i % 3 === 1 ? "mesen" : null,
    });
  });
}

// ── Meta ─────────────────────────────────────────────────────────

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

// ── Stories ──────────────────────────────────────────────────────

// Five states with screenshots — the headline case. Notice how the
// selected tile carries the brand ring + check badge.
export const FewStatesScreenshots: Story = {
  name: "States · 5 with screenshots",
  render: () => ({
    components: { AssetStrip },
    setup() {
      const states = manyStates(5);
      const selectedId = ref<number | null>(states[0].id);
      return {
        states,
        selectedId,
        onSelect: (a: StateSchema) => (selectedId.value = a.id),
      };
    },
    template: `
      <AssetStrip :assets="states" type="state" :selected-id="selectedId" @select="onSelect" />
    `,
  }),
};

// Twelve states — overflow case. Tiles scroll horizontally with snap.
export const ManyStatesOverflow: Story = {
  name: "States · 12 (horizontal scroll)",
  render: () => ({
    components: { AssetStrip },
    setup() {
      const states = manyStates(12);
      const selectedId = ref<number | null>(states[4].id);
      return {
        states,
        selectedId,
        onSelect: (a: StateSchema) => (selectedId.value = a.id),
      };
    },
    template: `
      <AssetStrip :assets="states" type="state" :selected-id="selectedId" @select="onSelect" />
    `,
  }),
};

// States that never had a screenshot taken — gradient fallback with
// the file icon. Still readable; the row doesn't feel broken.
export const StatesNoScreenshots: Story = {
  name: "States · 6 without screenshots",
  render: () => ({
    components: { AssetStrip },
    setup() {
      const states = manyStates(6, false);
      const selectedId = ref<number | null>(states[2].id);
      return {
        states,
        selectedId,
        onSelect: (a: StateSchema) => (selectedId.value = a.id),
      };
    },
    template: `
      <AssetStrip :assets="states" type="state" :selected-id="selectedId" @select="onSelect" />
    `,
  }),
};

// Long filenames should ellipsis cleanly without breaking the row.
export const LongFilenames: Story = {
  name: "Long filenames (ellipsis)",
  render: () => ({
    components: { AssetStrip },
    setup() {
      const states = [
        makeState({
          id: 1,
          file_name: "the_legend_of_zelda_a_link_to_the_past_speedrun_27.state",
          screenshot: {
            ...(makeState().screenshot as NonNullable<
              StateSchema["screenshot"]
            >),
            download_path:
              "https://placehold.co/640x360/2d2147/ffffff?text=LTTP",
          } as StateSchema["screenshot"],
        }),
        makeState({
          id: 2,
          file_name:
            "chrono_trigger_new_game_plus_attempt_third_run_boss_room.state",
          screenshot: {
            ...(makeState().screenshot as NonNullable<
              StateSchema["screenshot"]
            >),
            download_path:
              "https://placehold.co/640x360/4a1a1a/ffffff?text=CT+NG%2B",
          } as StateSchema["screenshot"],
        }),
        makeState({
          id: 3,
          file_name: "super_mario_world_special_world_complete_run.state",
          screenshot: null,
        }),
      ];
      const selectedId = ref<number | null>(states[0].id);
      return {
        states,
        selectedId,
        onSelect: (a: StateSchema) => (selectedId.value = a.id),
      };
    },
    template: `
      <AssetStrip :assets="states" type="state" :selected-id="selectedId" @select="onSelect" />
    `,
  }),
};

// Nothing selected yet — still shows a strip the user can click.
export const NoneSelected: Story = {
  name: "States · none selected",
  render: () => ({
    components: { AssetStrip },
    setup() {
      const states = manyStates(4);
      const selectedId = ref<number | null>(null);
      return {
        states,
        selectedId,
        onSelect: (a: StateSchema) => (selectedId.value = a.id),
      };
    },
    template: `
      <AssetStrip :assets="states" type="state" :selected-id="selectedId" @select="onSelect" />
    `,
  }),
};

// Empty — distinct from "no asset selected"; the strip itself is empty.
export const EmptyStates: Story = {
  name: "Empty (no states)",
  render: () => ({
    components: { AssetStrip },
    template: `
      <AssetStrip :assets="[]" type="state" :selected-id="null" />
    `,
  }),
};
