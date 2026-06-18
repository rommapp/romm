import type { Meta, StoryObj } from "@storybook/vue3-vite";
import { ref } from "vue";
import RComboboxField from "./RComboboxField.vue";

const meta: Meta<typeof RComboboxField> = {
  title: "Forms/RComboboxField",
  component: RComboboxField,
  argTypes: {
    label: { control: "text" },
    placeholder: { control: "text" },
    prefixLabel: {
      control: "inline-radio",
      options: [null, "stacked", "inline"],
    },
    variant: {
      control: "inline-radio",
      options: ["outlined", "filled", "underlined", "plain"],
    },
    density: {
      control: "inline-radio",
      options: ["default", "comfortable", "compact"],
    },
    disabled: { control: "boolean" },
    closableChips: { control: "boolean" },
    noSuggestions: { control: "boolean" },
  },
};

export default meta;
type Story = StoryObj<typeof RComboboxField>;

// ── Free-text, no suggestions ─────────────────────────────────

export const FreeText: Story = {
  name: "Free text (no items)",
  render: () => ({
    components: { RComboboxField },
    setup: () => ({ value: ref<string[]>([]) }),
    template: `
      <div style="width:320px;padding:24px">
        <RComboboxField
          v-model="value"
          label="Companies"
          prefix-label="stacked"
          variant="outlined"
          placeholder="Type and press Enter / comma to add"
        />
        <p style="margin-top:12px;font:12px monospace;color:var(--r-color-fg-muted)">
          {{ value }}
        </p>
      </div>
    `,
  }),
};

// ── With autocomplete suggestions ─────────────────────────────

export const WithSuggestions: Story = {
  name: "With autocomplete suggestions",
  render: () => ({
    components: { RComboboxField },
    setup: () => ({
      value: ref<string[]>([]),
      items: [
        "Single player",
        "Multiplayer",
        "Co-operative",
        "Split screen",
        "Massively multiplayer online (MMO)",
        "Battle Royale",
      ],
    }),
    template: `
      <div style="width:320px;padding:24px">
        <RComboboxField
          v-model="value"
          :items="items"
          label="Game modes"
          prefix-label="stacked"
          variant="outlined"
          placeholder="Pick or type"
          hint="Suggestions filter as you type. Custom values still commit."
        />
      </div>
    `,
  }),
};

// ── Pre-loaded with values ────────────────────────────────────

export const Preloaded: Story = {
  name: "Pre-loaded value",
  render: () => ({
    components: { RComboboxField },
    setup: () => ({
      value: ref<string[]>(["Nintendo", "Konami", "Capcom"]),
    }),
    template: `
      <div style="width:340px;padding:24px">
        <RComboboxField
          v-model="value"
          label="Companies"
          prefix-label="stacked"
          variant="outlined"
        />
      </div>
    `,
  }),
};

// ── Compact density ──────────────────────────────────────────

export const Compact: Story = {
  render: () => ({
    components: { RComboboxField },
    setup: () => ({ value: ref<string[]>(["Action", "RPG"]) }),
    template: `
      <div style="width:280px;padding:24px">
        <RComboboxField
          v-model="value"
          label="Genres"
          density="compact"
          prefix-label="inline"
          variant="outlined"
        />
      </div>
    `,
  }),
};

// ── Error state ──────────────────────────────────────────────

export const WithError: Story = {
  name: "Error state",
  render: () => ({
    components: { RComboboxField },
    setup: () => ({ value: ref<string[]>([]) }),
    template: `
      <div style="width:320px;padding:24px">
        <RComboboxField
          v-model="value"
          label="Required tags"
          prefix-label="stacked"
          variant="outlined"
          error-messages="At least one tag is required."
        />
      </div>
    `,
  }),
};

// ── Disabled ─────────────────────────────────────────────────

export const Disabled: Story = {
  render: () => ({
    components: { RComboboxField },
    setup: () => ({ value: ref<string[]>(["Locked", "Read only"]) }),
    template: `
      <div style="width:320px;padding:24px">
        <RComboboxField
          v-model="value"
          label="Locked field"
          prefix-label="stacked"
          variant="outlined"
          disabled
        />
      </div>
    `,
  }),
};

// ── Non-removable chips ──────────────────────────────────────

export const NonRemovable: Story = {
  name: "Non-removable chips",
  render: () => ({
    components: { RComboboxField },
    setup: () => ({ value: ref<string[]>(["Frozen", "Tag"]) }),
    template: `
      <div style="width:320px;padding:24px">
        <RComboboxField
          v-model="value"
          label="Frozen tags"
          prefix-label="stacked"
          variant="outlined"
          :closable-chips="false"
        />
      </div>
    `,
  }),
};
