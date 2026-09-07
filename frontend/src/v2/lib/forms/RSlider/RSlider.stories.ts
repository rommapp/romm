import type { Meta, StoryObj } from "@storybook/vue3-vite";
import { ref } from "vue";
import RSlider from "./RSlider.vue";

const meta: Meta<typeof RSlider> = {
  title: "Forms/RSlider",
  component: RSlider,
  // RSlider has no visible label, so every instance needs `ariaLabel`.
  args: { ariaLabel: "Value" },
  argTypes: {
    min: { control: "number" },
    max: { control: "number" },
    step: { control: "number" },
    color: { control: "text" },
    valuePosition: {
      control: "inline-radio",
      options: ["none", "left", "right", "thumb"],
    },
    valueSuffix: { control: "text" },
    showTicks: { control: "boolean" },
    disabled: { control: "boolean" },
    readonly: { control: "boolean" },
  },
  render: (args) => ({
    components: { RSlider },
    setup: () => {
      const value = ref(args.modelValue ?? 50);
      return { args, value };
    },
    template: `
      <div style="padding:24px;min-width:380px">
        <RSlider v-bind="args" v-model="value" />
        <div style="margin-top:12px;font-size:11px;color:var(--r-color-fg-muted)">
          value: {{ value }}
        </div>
      </div>
    `,
  }),
};

export default meta;
type Story = StoryObj<typeof RSlider>;

// ── Defaults ────────────────────────────────────────────────────────

export const Default: Story = { args: { modelValue: 50 } };

// ── Value badges ───────────────────────────────────────────────────

export const ValueRight: Story = {
  name: "Badge · right",
  args: { modelValue: 42, valuePosition: "right", valueSuffix: "%" },
};

export const ValueLeft: Story = {
  name: "Badge · left",
  args: { modelValue: 42, valuePosition: "left", valueSuffix: "%" },
};

export const ValueThumb: Story = {
  name: "Badge · floating thumb",
  args: { modelValue: 30, valuePosition: "thumb", valueSuffix: "%" },
};

// ── Steps + ticks ──────────────────────────────────────────────────

export const Stepped: Story = {
  name: "Stepped (10s)",
  args: { modelValue: 30, step: 10, showTicks: true },
};

export const FineSteps: Story = {
  name: "Fine steps (0.5)",
  args: { modelValue: 50, min: 0, max: 100, step: 0.5 },
};

// ── Range examples ─────────────────────────────────────────────────

export const Volume: Story = {
  name: "Volume (0–100)",
  args: {
    modelValue: 65,
    valuePosition: "right",
    valueSuffix: "%",
    color: "accent",
  },
};

export const Temperature: Story = {
  name: "Temperature",
  args: {
    modelValue: 22,
    min: 16,
    max: 30,
    step: 1,
    valuePosition: "thumb",
    valueSuffix: "°",
    color: "warning",
  },
};

// ── Color tones ────────────────────────────────────────────────────

export const ColorLadder: Story = {
  name: "Color ladder",
  render: () => ({
    components: { RSlider },
    setup: () => ({
      primary: ref(70),
      success: ref(70),
      warning: ref(70),
      danger: ref(70),
      info: ref(70),
    }),
    template: `
      <div style="display:flex;flex-direction:column;gap:18px;padding:24px;min-width:380px">
        <RSlider v-model="primary" color="primary" value-position="right" value-suffix="%" aria-label="Primary" />
        <RSlider v-model="success" color="success" value-position="right" value-suffix="%" aria-label="Success" />
        <RSlider v-model="warning" color="warning" value-position="right" value-suffix="%" aria-label="Warning" />
        <RSlider v-model="danger" color="danger" value-position="right" value-suffix="%" aria-label="Danger" />
        <RSlider v-model="info" color="info" value-position="right" value-suffix="%" aria-label="Info" />
      </div>
    `,
  }),
};

// ── States ─────────────────────────────────────────────────────────

export const Disabled: Story = {
  args: { modelValue: 40, disabled: true, valuePosition: "right" },
};

export const Readonly: Story = {
  args: { modelValue: 40, readonly: true, valuePosition: "right" },
};

// ── Commit-on-end pattern ──────────────────────────────────────────

export const CommitOnEnd: Story = {
  name: "Commit-on-end (@end)",
  render: () => ({
    components: { RSlider },
    setup: () => {
      const preview = ref(50);
      const committed = ref(50);
      function onEnd(v: number) {
        committed.value = v;
      }
      return { preview, committed, onEnd };
    },
    template: `
      <div style="padding:24px;min-width:380px;display:flex;flex-direction:column;gap:10px">
        <RSlider v-model="preview" value-position="thumb" value-suffix="%" aria-label="Volume" @end="onEnd" />
        <div style="font:12px sans-serif;color:var(--r-color-fg-muted)">
          previewing: {{ preview }} · last committed: {{ committed }}
        </div>
        <div style="font:11px sans-serif;color:var(--r-color-fg-faint)">
          Drag the thumb — preview updates live, committed only fires on release.
        </div>
      </div>
    `,
  }),
};
