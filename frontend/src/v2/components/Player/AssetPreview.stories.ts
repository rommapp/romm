import type { Meta, StoryObj } from "@storybook/vue3-vite";
import type { SaveSchema, StateSchema } from "@/__generated__";
import AssetPreview from "./AssetPreview.vue";

function makeSave(overrides: Partial<SaveSchema> = {}): SaveSchema {
  return {
    id: 1,
    rom_id: 1,
    user_id: 1,
    file_name: "main_quest.srm",
    file_name_no_tags: "main_quest.srm",
    file_name_no_ext: "main_quest",
    file_extension: "srm",
    file_path: "/saves/snes",
    file_size_bytes: 8192,
    full_path: "/saves/snes/main_quest.srm",
    download_path: "/api/saves/1/content",
    missing_from_fs: false,
    created_at: "2026-03-14T10:12:00Z",
    updated_at: "2026-05-23T18:45:00Z",
    emulator: "snes9x",
    slot: "main_quest",
    screenshot: null,
    ...overrides,
  } as SaveSchema;
}

function makeState(
  fileName: string,
  shotUrl: string | null,
  overrides: Partial<StateSchema> = {},
): StateSchema {
  return {
    id: 1,
    rom_id: 1,
    user_id: 1,
    file_name: fileName,
    file_name_no_tags: fileName,
    file_name_no_ext: fileName.replace(/\.state$/, ""),
    file_extension: "state",
    file_path: "/states/snes",
    file_size_bytes: 524288,
    full_path: `/states/snes/${fileName}`,
    download_path: "/api/states/1/content",
    missing_from_fs: false,
    created_at: "2026-04-02T09:00:00Z",
    updated_at: "2026-05-25T18:08:00Z",
    emulator: "snes9x",
    screenshot: shotUrl
      ? ({
          id: 1,
          rom_id: 1,
          user_id: 1,
          file_name: `${fileName}.png`,
          file_name_no_tags: `${fileName}.png`,
          file_name_no_ext: fileName,
          file_extension: "png",
          file_path: "/screenshots/snes",
          download_path: shotUrl,
        } as StateSchema["screenshot"])
      : null,
    ...overrides,
  } as StateSchema;
}

const meta: Meta<typeof AssetPreview> = {
  title: "Player/AssetPreview",
  component: AssetPreview,
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
type Story = StoryObj<typeof AssetPreview>;

// State with a screenshot — the headline case.
export const StateWithScreenshot: Story = {
  name: "State · with screenshot",
  render: () => ({
    components: { AssetPreview },
    setup: () => ({
      asset: makeState(
        "before_final_boss.state",
        "https://placehold.co/640x360/4a1a1a/ffffff?text=Before+Boss",
      ),
    }),
    template: `<AssetPreview :asset="asset" type="state" />`,
  }),
};

// State that never had a screenshot — placeholder + icon.
export const StateNoScreenshot: Story = {
  name: "State · no screenshot",
  render: () => ({
    components: { AssetPreview },
    setup: () => ({
      asset: makeState("forgot_screenshot.state", null),
    }),
    template: `<AssetPreview :asset="asset" type="state" />`,
  }),
};

// Save selected — saves don't have screenshots; we lean on metadata.
export const SaveSelected: Story = {
  name: "Save · selected",
  render: () => ({
    components: { AssetPreview },
    setup: () => ({ asset: makeSave() }),
    template: `<AssetPreview :asset="asset" type="save" />`,
  }),
};

// Long filename should ellipsis cleanly.
export const LongFilename: Story = {
  name: "Long filename",
  render: () => ({
    components: { AssetPreview },
    setup: () => ({
      asset: makeState(
        "chrono_trigger_new_game_plus_attempt_03_post_lavos_alternate_ending.state",
        "https://placehold.co/640x360/2d2147/ffffff?text=Chrono",
      ),
    }),
    template: `<AssetPreview :asset="asset" type="state" />`,
  }),
};

// No state selected — empty state with the start-fresh hint.
export const EmptyNoState: Story = {
  name: "Empty · no state selected",
  render: () => ({
    components: { AssetPreview },
    template: `<AssetPreview :asset="null" type="state" />`,
  }),
};

export const EmptyNoSave: Story = {
  name: "Empty · no save selected",
  render: () => ({
    components: { AssetPreview },
    template: `<AssetPreview :asset="null" type="save" />`,
  }),
};
