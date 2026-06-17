import type { Meta, StoryObj } from "@storybook/vue3-vite";
import type { SaveSchema, StateSchema } from "@/__generated__";
import AssetCard from "./AssetCard.vue";

// Helper builders — avoid spamming the same shape into every story.
function makeSave(overrides: Partial<SaveSchema> = {}): SaveSchema {
  return {
    id: 1,
    rom_id: 1,
    user_id: 1,
    file_name: "super_mario_world_slot1.srm",
    file_name_no_tags: "super_mario_world_slot1.srm",
    file_name_no_ext: "super_mario_world_slot1",
    file_extension: "srm",
    file_path: "/saves/snes",
    file_size_bytes: 8192,
    full_path: "/saves/snes/super_mario_world_slot1.srm",
    download_path: "/api/saves/1/content",
    missing_from_fs: false,
    created_at: "2026-03-14T10:12:00Z",
    updated_at: "2026-05-10T18:45:00Z",
    emulator: "snes9x",
    screenshot: null,
    ...overrides,
  } as SaveSchema;
}

function makeState(overrides: Partial<StateSchema> = {}): StateSchema {
  return {
    id: 1,
    rom_id: 1,
    user_id: 1,
    file_name: "chrono_trigger_quicksave.state",
    file_name_no_tags: "chrono_trigger_quicksave.state",
    file_name_no_ext: "chrono_trigger_quicksave",
    file_extension: "state",
    file_path: "/states/snes",
    file_size_bytes: 524288,
    full_path: "/states/snes/chrono_trigger_quicksave.state",
    download_path: "/api/states/1/content",
    missing_from_fs: false,
    created_at: "2026-04-02T09:00:00Z",
    updated_at: "2026-05-13T22:08:00Z",
    emulator: "snes9x",
    screenshot: {
      id: 1,
      rom_id: 1,
      user_id: 1,
      file_name: "chrono_trigger_quicksave.png",
      file_name_no_tags: "chrono_trigger_quicksave.png",
      file_name_no_ext: "chrono_trigger_quicksave",
      file_extension: "png",
      file_path: "/screenshots/snes",
      // Use a placeholder cover so the story renders something
      // recognisable in the 16:9 slot.
      download_path:
        "https://placehold.co/640x360/2d2147/ffffff?text=Quicksave",
    } as StateSchema["screenshot"],
    ...overrides,
  } as StateSchema;
}

const meta: Meta<typeof AssetCard> = {
  title: "Media/AssetCard",
  component: AssetCard,
  argTypes: {
    type: { control: "inline-radio", options: ["save", "state"] },
  },
};

export default meta;

type Story = StoryObj<typeof AssetCard>;

// ── Save (no screenshot) ────────────────────────────────────────

export const Save: Story = {
  render: () => ({
    components: { AssetCard },
    setup: () => ({ asset: makeSave() }),
    template: `
      <div style="width:200px">
        <AssetCard :asset="asset" type="save" />
      </div>
    `,
  }),
};

// ── Save without emulator chip ─────────────────────────────────

export const SaveNoEmulator: Story = {
  name: "Save (no emulator)",
  render: () => ({
    components: { AssetCard },
    setup: () => ({ asset: makeSave({ emulator: null }) }),
    template: `
      <div style="width:200px">
        <AssetCard :asset="asset" type="save" />
      </div>
    `,
  }),
};

// ── State (with screenshot) ─────────────────────────────────────

export const State: Story = {
  render: () => ({
    components: { AssetCard },
    setup: () => ({ asset: makeState() }),
    template: `
      <div style="width:240px">
        <AssetCard :asset="asset" type="state" />
      </div>
    `,
  }),
};

// ── State without a screenshot (placeholder pattern) ────────────

export const StateNoScreenshot: Story = {
  name: "State (placeholder screenshot)",
  render: () => ({
    components: { AssetCard },
    setup: () => ({
      asset: makeState({
        file_name: "earthbound_save_4.state",
        screenshot: null,
      }),
    }),
    template: `
      <div style="width:240px">
        <AssetCard :asset="asset" type="state" />
      </div>
    `,
  }),
};

// ── Long filename — ellipsis path ──────────────────────────────

export const LongFilename: Story = {
  name: "Long filename",
  render: () => ({
    components: { AssetCard },
    setup: () => ({
      asset: makeSave({
        file_name:
          "the_legend_of_zelda_a_link_to_the_past_speedrun_attempt_27.srm",
        file_size_bytes: 64 * 1024,
      }),
    }),
    template: `
      <div style="width:200px">
        <AssetCard :asset="asset" type="save" />
      </div>
    `,
  }),
};

// ── Grid layout (real picker context) ──────────────────────────

export const Grid: Story = {
  name: "Grid (picker layout)",
  render: () => ({
    components: { AssetCard },
    setup: () => {
      const states: StateSchema[] = [
        makeState({ id: 1, file_name: "chrono_trigger_1.state" }),
        makeState({
          id: 2,
          file_name: "chrono_trigger_2.state",
          screenshot: {
            ...(makeState().screenshot as NonNullable<
              StateSchema["screenshot"]
            >),
            download_path:
              "https://placehold.co/640x360/1a3d2e/ffffff?text=Forest+Save",
          },
        }),
        makeState({
          id: 3,
          file_name: "chrono_trigger_3.state",
          emulator: null,
          screenshot: null,
        }),
        makeState({
          id: 4,
          file_name: "chrono_trigger_boss.state",
          file_size_bytes: 1 * 1024 * 1024,
          screenshot: {
            ...(makeState().screenshot as NonNullable<
              StateSchema["screenshot"]
            >),
            download_path:
              "https://placehold.co/640x360/4a1a1a/ffffff?text=Boss+Fight",
          },
        }),
      ];
      return { states };
    },
    template: `
      <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:12px;width:600px;padding:8px">
        <AssetCard v-for="s in states" :key="s.id" :asset="s" type="state" />
      </div>
    `,
  }),
};
