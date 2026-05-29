import type { Meta, StoryObj } from "@storybook/vue3-vite";
import { ref } from "vue";
import RProgressLinear from "./RProgressLinear.vue";

const meta: Meta<typeof RProgressLinear> = {
  title: "Primitives/RProgressLinear",
  component: RProgressLinear,
  argTypes: {
    modelValue: { control: { type: "range", min: 0, max: 100, step: 1 } },
    bufferValue: { control: { type: "range", min: 0, max: 100, step: 1 } },
    height: { control: "text" },
    color: { control: "text" },
    indeterminate: { control: "boolean" },
    rounded: { control: "boolean" },
    striped: { control: "boolean" },
  },
};

export default meta;
type Story = StoryObj<typeof RProgressLinear>;

// ── Determinate (default) ────────────────────────────────────

export const Default: Story = {
  args: { modelValue: 42 },
  render: (args) => ({
    components: { RProgressLinear },
    setup: () => ({ args }),
    template: `
      <div style="width:360px;padding:24px">
        <RProgressLinear v-bind="args" />
      </div>
    `,
  }),
};

// ── Tones ────────────────────────────────────────────────────

export const Tones: Story = {
  render: () => ({
    components: { RProgressLinear },
    template: `
      <div style="width:360px;padding:24px;display:flex;flex-direction:column;gap:16px">
        <RProgressLinear :model-value="55" color="primary" />
        <RProgressLinear :model-value="55" color="success" />
        <RProgressLinear :model-value="55" color="warning" />
        <RProgressLinear :model-value="55" color="danger" />
        <RProgressLinear :model-value="55" color="info" />
      </div>
    `,
  }),
};

// ── Indeterminate ────────────────────────────────────────────

export const Indeterminate: Story = {
  args: { indeterminate: true, color: "primary" },
  render: (args) => ({
    components: { RProgressLinear },
    setup: () => ({ args }),
    template: `
      <div style="width:360px;padding:24px">
        <RProgressLinear v-bind="args" />
      </div>
    `,
  }),
};

// ── Buffered (streaming) ────────────────────────────────────

export const Buffered: Story = {
  name: "Buffered (streaming)",
  render: () => ({
    components: { RProgressLinear },
    setup: () => ({ value: 42, buffer: 78 }),
    template: `
      <div style="width:360px;padding:24px">
        <RProgressLinear :model-value="value" :buffer-value="buffer" />
        <p style="margin-top:8px;font-size:12px;color:var(--r-color-fg-muted)">
          Played: {{ value }}% · Buffered: {{ buffer }}%
        </p>
      </div>
    `,
  }),
};

// ── Heights ──────────────────────────────────────────────────

export const Heights: Story = {
  render: () => ({
    components: { RProgressLinear },
    template: `
      <div style="width:360px;padding:24px;display:flex;flex-direction:column;gap:16px">
        <RProgressLinear :model-value="60" :height="2" />
        <RProgressLinear :model-value="60" :height="4" />
        <RProgressLinear :model-value="60" :height="8" />
        <RProgressLinear :model-value="60" :height="16" />
      </div>
    `,
  }),
};

// ── Striped (active emphasis) ─────────────────────────────

export const Striped: Story = {
  name: "Striped (active emphasis)",
  args: { modelValue: 65, striped: true, height: 12, color: "primary" },
  render: (args) => ({
    components: { RProgressLinear },
    setup: () => ({ args }),
    template: `
      <div style="width:360px;padding:24px">
        <RProgressLinear v-bind="args" />
      </div>
    `,
  }),
};

// ── With external label (typical compose pattern) ──────────

export const WithLabel: Story = {
  name: "With external label",
  render: () => ({
    components: { RProgressLinear },
    setup: () => ({ value: ref(72) }),
    template: `
      <div style="width:360px;padding:24px;display:flex;flex-direction:column;gap:8px">
        <div style="display:flex;justify-content:space-between;font-size:12px;color:var(--r-color-fg-muted)">
          <span>Uploading mega-man-x.zip</span>
          <span>{{ value }}%</span>
        </div>
        <RProgressLinear :model-value="value" />
      </div>
    `,
  }),
};

// ── Live ticker (animated demo) ────────────────────────────

export const LiveTicker: Story = {
  name: "Live ticker (animated)",
  render: () => ({
    components: { RProgressLinear },
    setup() {
      const value = ref(0);
      let frame = 0;
      function step() {
        frame += 1;
        value.value = (frame % 100) + 1;
        requestAnimationFrame(() => setTimeout(step, 80));
      }
      step();
      return { value };
    },
    template: `
      <div style="width:360px;padding:24px">
        <RProgressLinear :model-value="value" color="success" :height="6" striped />
      </div>
    `,
  }),
};
