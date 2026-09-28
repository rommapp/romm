import type { Meta, StoryObj } from "@storybook/vue3-vite";
import type { SaveSchema, StateSchema } from "@/__generated__";
import {
  hoursAgo,
  makeSave,
  makeState,
  screenshotFixture,
} from "@/v2/utils/saveStates.fixtures";
import AssetPreview from "./AssetPreview.vue";

function save(overrides: Partial<SaveSchema> = {}): SaveSchema {
  return makeSave(1, "main_quest", 49, {
    created_at: hoursAgo(72 * 24),
    ...overrides,
  });
}

function namedState(fileName: string, shotUrl: string | null): StateSchema {
  return makeState({
    file_name: fileName,
    file_name_no_tags: fileName,
    file_name_no_ext: fileName.replace(/\.state$/, ""),
    full_path: `/states/snes/${fileName}`,
    updated_at: hoursAgo(2),
    screenshot: shotUrl ? screenshotFixture(shotUrl) : null,
  });
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

// State with a screenshot, the headline case.
export const StateWithScreenshot: Story = {
  name: "State · with screenshot",
  args: {
    asset: namedState(
      "before_final_boss.state",
      "https://placehold.co/640x360/4a1a1a/ffffff?text=Before+Boss",
    ),
    type: "state",
  },
};

// A state that never had a screenshot falls back to a placeholder icon.
export const StateNoScreenshot: Story = {
  name: "State · no screenshot",
  args: { asset: namedState("forgot_screenshot.state", null), type: "state" },
};

// Saves rarely carry a screenshot, so the preview leans on metadata.
export const SaveSelected: Story = {
  name: "Save · selected",
  args: { asset: save(), type: "save" },
};

export const SaveWithScreenshot: Story = {
  name: "Save · with screenshot",
  args: {
    asset: save({
      screenshot: screenshotFixture(
        "https://placehold.co/640x360/1a3d2e/ffffff?text=Main+Quest",
        2,
      ),
    }),
    type: "save",
  },
};

// A state is armed, so the save is the write-back target, not what boots.
export const SaveAsWriteTarget: Story = {
  name: "Save · write-back target",
  args: { asset: save(), type: "save", stateArmed: true },
};

export const EmptySaveWithStateArmed: Story = {
  name: "Empty · no save, state armed",
  args: { asset: null, type: "save", stateArmed: true },
};

// Long filename should ellipsis cleanly.
export const LongFilename: Story = {
  name: "Long filename",
  args: {
    asset: namedState(
      "chrono_trigger_new_game_plus_attempt_03_post_lavos_alternate_ending.state",
      "https://placehold.co/640x360/2d2147/ffffff?text=Chrono",
    ),
    type: "state",
  },
};

// No state selected: the empty state with the start-fresh hint.
export const EmptyNoState: Story = {
  name: "Empty · no state selected",
  args: { asset: null, type: "state" },
};

export const EmptyNoSave: Story = {
  name: "Empty · no save selected",
  args: { asset: null, type: "save" },
};
