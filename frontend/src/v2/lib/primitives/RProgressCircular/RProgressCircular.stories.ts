import type { Meta, StoryObj } from "@storybook/vue3-vite";
import { onMounted, onUnmounted, ref } from "vue";
import RProgressCircular from "./RProgressCircular.vue";

const meta: Meta<typeof RProgressCircular> = {
  title: "Primitives/RProgressCircular",
  component: RProgressCircular,
  argTypes: {
    indeterminate: { control: "boolean" },
    size: { control: "number" },
    width: { control: "number" },
    color: { control: "text" },
    modelValue: { control: { type: "range", min: 0, max: 100 } },
  },
};

export default meta;

type Story = StoryObj<typeof RProgressCircular>;

// ── Defaults ────────────────────────────────────────────────────────

export const Indeterminate: Story = {
  args: { indeterminate: true, size: 32 },
};

export const Determinate: Story = {
  args: { indeterminate: false, modelValue: 65, size: 64, width: 4 },
};

// ── Size ladder ─────────────────────────────────────────────────────

export const SizeLadder: Story = {
  name: "Size ladder · indeterminate",
  render: () => ({
    components: { RProgressCircular },
    template: `
      <div style="display:flex;align-items:flex-end;gap:24px;font:11px/1.2 sans-serif;color:var(--r-color-fg-muted)">
        <div style="display:flex;flex-direction:column;align-items:center;gap:8px">
          <RProgressCircular indeterminate :size="16" :width="2" />
          <span>16 / 2</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:8px">
          <RProgressCircular indeterminate :size="24" :width="2" />
          <span>24 / 2</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:8px">
          <RProgressCircular indeterminate :size="36" :width="3" />
          <span>36 / 3</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:8px">
          <RProgressCircular indeterminate :size="56" :width="4" />
          <span>56 / 4</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:8px">
          <RProgressCircular indeterminate :size="80" :width="6" />
          <span>80 / 6</span>
        </div>
      </div>
    `,
  }),
};

export const DeterminateLadder: Story = {
  name: "Determinate · stepped values",
  render: () => ({
    components: { RProgressCircular },
    template: `
      <div style="display:flex;align-items:flex-end;gap:24px;font:11px/1.2 sans-serif;color:var(--r-color-fg-muted)">
        <div style="display:flex;flex-direction:column;align-items:center;gap:8px">
          <RProgressCircular :indeterminate="false" :model-value="0" :size="48" :width="4" />
          <span>0%</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:8px">
          <RProgressCircular :indeterminate="false" :model-value="25" :size="48" :width="4" />
          <span>25%</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:8px">
          <RProgressCircular :indeterminate="false" :model-value="50" :size="48" :width="4" />
          <span>50%</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:8px">
          <RProgressCircular :indeterminate="false" :model-value="75" :size="48" :width="4" />
          <span>75%</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:8px">
          <RProgressCircular :indeterminate="false" :model-value="100" :size="48" :width="4" />
          <span>100%</span>
        </div>
      </div>
    `,
  }),
};

// ── Tones ───────────────────────────────────────────────────────────

export const Tones: Story = {
  render: () => ({
    components: { RProgressCircular },
    template: `
      <div style="display:grid;grid-template-columns:repeat(4,auto);gap:24px 32px;font:11px/1.2 sans-serif;color:var(--r-color-fg-muted)">
        <div style="display:flex;flex-direction:column;align-items:center;gap:8px">
          <RProgressCircular color="primary" :size="40" :width="3" />
          <span>primary</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:8px">
          <RProgressCircular color="secondary" :size="40" :width="3" />
          <span>secondary</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:8px">
          <RProgressCircular color="accent" :size="40" :width="3" />
          <span>accent</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:8px">
          <RProgressCircular color="success" :size="40" :width="3" />
          <span>success</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:8px">
          <RProgressCircular color="warning" :size="40" :width="3" />
          <span>warning</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:8px">
          <RProgressCircular color="danger" :size="40" :width="3" />
          <span>danger</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:8px">
          <RProgressCircular color="info" :size="40" :width="3" />
          <span>info</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:8px">
          <RProgressCircular color="romm-gold" :size="40" :width="3" />
          <span>romm-gold</span>
        </div>
      </div>
    `,
  }),
};

// ── Slot ─────────────────────────────────────────────────────────────

export const WithLabel: Story = {
  name: "Default slot (percentage label)",
  render: () => ({
    components: { RProgressCircular },
    template: `
      <div style="display:flex;gap:24px;align-items:flex-end;font:11px/1.2 sans-serif;color:var(--r-color-fg-muted)">
        <div style="display:flex;flex-direction:column;align-items:center;gap:8px">
          <RProgressCircular :indeterminate="false" :model-value="35" :size="64" :width="4">
            35%
          </RProgressCircular>
          <span>numeric</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:8px">
          <RProgressCircular :indeterminate="false" :model-value="80" :size="80" :width="5" color="success">
            <span style="font-size:14px">80%</span>
          </RProgressCircular>
          <span>larger + custom font-size</span>
        </div>
      </div>
    `,
  }),
};

// ── Live progress ───────────────────────────────────────────────────

export const Animated: Story = {
  name: "Animated progress (live update)",
  render: () => ({
    components: { RProgressCircular },
    setup() {
      const value = ref(0);
      let timer: ReturnType<typeof setInterval> | undefined;
      onMounted(() => {
        timer = setInterval(() => {
          value.value = (value.value + 5) % 105;
          if (value.value > 100) value.value = 0;
        }, 400);
      });
      onUnmounted(() => {
        if (timer) clearInterval(timer);
      });
      return { value };
    },
    template: `
      <div style="display:flex;flex-direction:column;align-items:center;gap:14px;font:12px/1.4 sans-serif;color:var(--r-color-fg-muted)">
        <RProgressCircular :indeterminate="false" :model-value="value" :size="80" :width="5" color="primary">
          <span style="font-size:14px;font-weight:600">{{ value }}%</span>
        </RProgressCircular>
        <span>Value advances every 400ms — note the smooth fill transition.</span>
      </div>
    `,
  }),
};

// ── Comparison ──────────────────────────────────────────────────────

export const InContext: Story = {
  name: "Inline in buttons / dialogs",
  render: () => ({
    components: { RProgressCircular },
    template: `
      <div style="display:flex;flex-direction:column;gap:18px;font:13px/1.4 sans-serif;color:var(--r-color-fg)">
        <button
          type="button"
          style="display:inline-flex;align-items:center;gap:8px;padding:8px 14px;background:var(--r-color-brand-primary);color:white;border:none;border-radius:6px;font-weight:600;cursor:wait;align-self:flex-start"
          disabled
        >
          <RProgressCircular indeterminate :size="14" :width="2" color="white" />
          Submitting…
        </button>
        <div style="display:flex;align-items:center;gap:14px;padding:16px;background:var(--r-color-surface);border-radius:12px;align-self:flex-start">
          <RProgressCircular indeterminate :size="36" :width="3" color="primary" />
          <div style="display:flex;flex-direction:column;gap:2px">
            <span style="font-weight:600">Fetching metadata</span>
            <span style="color:var(--r-color-fg-muted);font-size:11px">This may take a few seconds…</span>
          </div>
        </div>
      </div>
    `,
  }),
};
