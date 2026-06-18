import type { Meta, StoryObj } from "@storybook/vue3-vite";
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
    hideFooter: { control: "boolean" },
    disabled: { control: "boolean" },
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
