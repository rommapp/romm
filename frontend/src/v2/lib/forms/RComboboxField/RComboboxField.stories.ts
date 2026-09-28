import type { Meta, StoryObj } from "@storybook/vue3-vite";
import { RBtn, RForm } from "@v2/lib";
import { expect, userEvent } from "storybook/test";
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

// ── Rules, checked through an enclosing RForm ─────────────────

export const Required: Story = {
  name: "Required (rules in a form)",
  render: () => ({
    components: { RComboboxField, RForm, RBtn },
    setup() {
      const value = ref<string[]>([]);
      const formRef = ref<{ validate: () => Promise<unknown> } | null>(null);
      const rules = [
        (items: string[]) => items.length > 0 || "Add at least one tag.",
      ];
      return { value, formRef, rules };
    },
    template: `
      <RForm ref="formRef" style="width:320px;padding:24px;display:flex;flex-direction:column;gap:12px">
        <RComboboxField
          v-model="value"
          label="Tags"
          prefix-label="stacked"
          :rules="rules"
          no-suggestions
        />
        <RBtn @click="formRef?.validate()">Validate</RBtn>
      </RForm>
    `,
  }),
  play: async ({ canvasElement, step }) => {
    const input = canvasElement.querySelector(
      ".r-combobox-field input",
    ) as HTMLInputElement;
    const validate = canvasElement.querySelector("button") as HTMLElement;

    await step("an empty list fails", async () => {
      await userEvent.click(validate);
      await expect(canvasElement.textContent).toContain(
        "Add at least one tag.",
      );
    });
    await step("a committed chip clears the error", async () => {
      await userEvent.type(input, "rpg{enter}");
      await expect(canvasElement.textContent).not.toContain(
        "Add at least one tag.",
      );
    });
  },
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
