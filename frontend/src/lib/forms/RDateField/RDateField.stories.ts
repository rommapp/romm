import type { Meta, StoryObj } from "@storybook/vue3-vite";
import { expect, userEvent, waitFor, within } from "storybook/test";
import { ref } from "vue";
import RDateField from "./RDateField.vue";

const meta: Meta<typeof RDateField> = {
  title: "Forms/RDateField",
  component: RDateField,
  argTypes: {
    firstDayOfWeek: {
      control: "inline-radio",
      options: [0, 1, 2, 3, 4, 5, 6],
    },
  },
};

export default meta;
type Story = StoryObj<typeof RDateField>;

export const Default: Story = {
  render: () => ({
    components: { RDateField },
    setup: () => ({ value: ref<Date | null>(null) }),
    template: `
      <div style="width:280px;padding:24px">
        <RDateField
          v-model="value"
          label="Released at"
          variant="outlined"
          prefix-label="stacked"
        />
        <p style="margin-top:12px;font:12px monospace;color:var(--r-color-fg-muted)">
          Date: {{ value?.toISOString() ?? 'null' }}<br>
          Timestamp: {{ value?.getTime() ?? 'null' }}
        </p>
      </div>
    `,
  }),
};

export const Preloaded: Story = {
  name: "Pre-loaded (timestamp)",
  render: () => ({
    components: { RDateField },
    setup: () => ({
      value: ref<number | Date | null>(1_700_000_000_000),
    }),
    template: `
      <div style="width:280px;padding:24px">
        <RDateField
          v-model="value"
          label="Released at"
          variant="outlined"
          prefix-label="stacked"
        />
      </div>
    `,
  }),
};

export const Compact: Story = {
  render: () => ({
    components: { RDateField },
    setup: () => ({ value: ref<Date | null>(null) }),
    template: `
      <div style="width:240px;padding:24px">
        <RDateField
          v-model="value"
          label="Date"
          density="compact"
          variant="outlined"
          prefix-label="inline"
        />
      </div>
    `,
  }),
};

export const SundayFirst: Story = {
  name: "Sunday-first week",
  render: () => ({
    components: { RDateField },
    setup: () => ({ value: ref<Date | null>(null) }),
    template: `
      <div style="width:280px;padding:24px">
        <RDateField
          v-model="value"
          label="US format"
          variant="outlined"
          prefix-label="stacked"
          :first-day-of-week="0"
        />
      </div>
    `,
  }),
};

export const WithBounds: Story = {
  name: "Min / max",
  render: () => ({
    components: { RDateField },
    setup: () => ({
      value: ref<Date | null>(null),
      min: new Date(2026, 4, 1),
      max: new Date(2026, 5, 30),
    }),
    template: `
      <div style="width:280px;padding:24px">
        <RDateField
          v-model="value"
          label="May → June 2026 only"
          variant="outlined"
          prefix-label="stacked"
          :min="min"
          :max="max"
        />
      </div>
    `,
  }),
};

export const NoFooter: Story = {
  name: "Without footer",
  render: () => ({
    components: { RDateField },
    setup: () => ({ value: ref<Date | null>(null) }),
    template: `
      <div style="width:280px;padding:24px">
        <RDateField
          v-model="value"
          label="No shortcuts"
          variant="outlined"
          prefix-label="stacked"
          hide-footer
        />
      </div>
    `,
  }),
};

export const Disabled: Story = {
  render: () => ({
    components: { RDateField },
    setup: () => ({ value: ref(new Date("2026-05-14")) }),
    template: `
      <div style="width:280px;padding:24px">
        <RDateField
          v-model="value"
          label="Locked date"
          variant="outlined"
          prefix-label="stacked"
          disabled
        />
      </div>
    `,
  }),
};

export const KeyboardSelection: Story = {
  name: "Keyboard selection (play)",
  render: () => ({
    components: { RDateField },
    setup: () => ({ value: ref<Date | null>(null) }),
    template: `
      <div style="width:280px;padding:24px">
        <RDateField v-model="value" label="Released at" variant="outlined" />
      </div>
    `,
  }),
  play: async ({ canvasElement, step }) => {
    const field = await within(canvasElement).findByRole("combobox", {
      name: "Released at",
    });
    // The picker teleports to <body>, outside the story canvas.
    const panel = () => document.querySelector('[role="dialog"]');

    await step("Enter opens the picker on a day", async () => {
      field.focus();
      await userEvent.keyboard("{Enter}");
      await waitFor(() => expect(panel()).not.toBeNull());
      await expect(field).toHaveAttribute("aria-expanded", "true");
      await waitFor(() =>
        expect(document.activeElement).toHaveClass("r-date-cal__day"),
      );
    });

    await step("Arrow keys move between days and Enter picks one", async () => {
      const start = document.activeElement;
      await userEvent.keyboard("{ArrowRight}");
      await expect(document.activeElement).not.toBe(start);
      await userEvent.keyboard("{Enter}");
      await waitFor(() => expect(panel()).toBeNull());
      await expect(field).not.toHaveValue("");
      await expect(field).toHaveAttribute("aria-expanded", "false");
    });
  },
};

export const GamepadPick: Story = {
  name: "Gamepad · pick a day with A (play)",
  render: () => ({
    components: { RDateField },
    setup: () => ({ value: ref<Date | null>(new Date(Date.UTC(2024, 2, 15))) }),
    template: `
      <div style="width:280px;padding:24px">
        <RDateField v-model="value" label="Released at" variant="outlined" />
      </div>
    `,
  }),
  play: async ({ canvasElement, step }) => {
    const field = await within(canvasElement).findByRole("combobox", {
      name: "Released at",
    });
    const panel = () => document.querySelector('[role="dialog"]');

    await step("D-pad moves between days and A picks one", async () => {
      field.focus();
      await userEvent.keyboard("{Enter}");
      await waitFor(() =>
        expect(document.activeElement).toHaveAttribute(
          "data-value",
          "2024-03-15",
        ),
      );
      // `useGamepad` sends the D-pad as arrow keys and presses A as `.click()`.
      await userEvent.keyboard("{ArrowDown}{ArrowRight}");
      (document.activeElement as HTMLElement).click();
      await waitFor(() => expect(panel()).toBeNull());
      await expect(field).toHaveValue("Mar 23, 2024");
    });
  },
};
