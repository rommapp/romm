import type { Meta, StoryObj } from "@storybook/vue3-vite";
import { expect, userEvent } from "storybook/test";
import { computed, ref } from "vue";
import RCheckbox from "./RCheckbox.vue";
import type { RCheckboxState } from "./types";

// Permission-matrix vocabulary: empty -> full (primary check) -> own
// (accent person). A fourth danger state shows the 4-state override flavour.
const GRANT_STATES: RCheckboxState[] = [
  { value: "none" },
  { value: "full", color: "primary" },
  { value: "own", color: "accent", icon: "mdi-account" },
];
const OVERRIDE_STATES: RCheckboxState[] = [
  { value: "inherit" },
  { value: "grant", color: "primary" },
  { value: "grant_own", color: "accent", icon: "mdi-account" },
  { value: "revoke", color: "danger", icon: "mdi-close" },
];

const meta: Meta<typeof RCheckbox> = {
  title: "Forms/RCheckbox",
  component: RCheckbox,
  argTypes: {
    label: { control: "text" },
    subtitle: { control: "text" },
    size: {
      control: "inline-radio",
      options: ["xs", "sm", "md", "lg"],
    },
    shape: {
      control: "inline-radio",
      options: ["square", "rounded", "circle"],
    },
    color: { control: "text" },
    variant: {
      control: "inline-radio",
      options: ["box", "card"],
    },
    disabled: { control: "boolean" },
    indeterminate: { control: "boolean" },
    bare: { control: "boolean" },
    error: { control: "boolean" },
    errorMessages: { control: "text" },
  },
  render: (args) => ({
    components: { RCheckbox },
    setup: () => {
      const value = ref(false);
      return { args, value };
    },
    template: `<RCheckbox v-model="value" v-bind="args" />`,
  }),
};

export default meta;

type Story = StoryObj<typeof RCheckbox>;

// ── Defaults ────────────────────────────────────────────────────────

export const Default: Story = {
  args: { label: "Remember me" },
};

export const Checked: Story = {
  args: { label: "Auto-login next time" },
  render: (args) => ({
    components: { RCheckbox },
    setup: () => {
      const value = ref(true);
      return { args, value };
    },
    template: `<RCheckbox v-model="value" v-bind="args" />`,
  }),
};

export const Indeterminate: Story = {
  args: { label: "Some items selected", indeterminate: true },
};

export const NoLabel: Story = { args: {} };

// ── Multi-state ─────────────────────────────────────────────────────

// `states` opts into an N-value control on its own `stateValue` model,
// leaving the boolean `modelValue` path untouched. Clicking cycles through
// the ordered list (first = empty); a state with a `color` fills the box
// and with an `icon` shows that glyph (else the check tick).
export const MultiState: Story = {
  name: "Multi-state (none / full / own)",
  render: () => ({
    components: { RCheckbox },
    setup() {
      const state = ref<string>("none");
      return { state, GRANT_STATES };
    },
    template: `
      <div style="display:flex;flex-direction:column;align-items:flex-start;gap:12px;font:12px/1.4 sans-serif;color:var(--r-color-fg-muted)">
        <RCheckbox
          v-model:state-value="state"
          :states="GRANT_STATES"
          aria-label="Permission"
          label="Click to cycle: none → full → own"
        />
        <span>Current value: <strong>{{ state }}</strong></span>
      </div>
    `,
  }),
  play: async ({ canvasElement, step }) => {
    const label = canvasElement.querySelector(".r-checkbox") as HTMLElement;
    const wrap = canvasElement.querySelector(".r-checkbox-wrap") as HTMLElement;

    await step("none → full (check, primary)", async () => {
      await userEvent.click(label);
      await expect(wrap.classList.contains("r-checkbox--multi-active")).toBe(
        true,
      );
      await expect(wrap.classList.contains("r-checkbox--multi-check")).toBe(
        true,
      );
    });
    await step("full → own (account, accent)", async () => {
      await userEvent.click(label);
      await expect(wrap.classList.contains("r-checkbox--multi-icon")).toBe(
        true,
      );
    });
    await step("own → none (empty)", async () => {
      await userEvent.click(label);
      await expect(wrap.classList.contains("r-checkbox--multi-active")).toBe(
        false,
      );
    });
  },
};

// The override flavour cycles through four states — inherit, grant
// (primary), grant-own (accent), revoke (danger).
export const MultiStateLadder: Story = {
  name: "Multi-state ladder (4-state override)",
  render: () => ({
    components: { RCheckbox },
    setup() {
      const inherit = ref("inherit");
      const grant = ref("grant");
      const grantOwn = ref("grant_own");
      const revoke = ref("revoke");
      return { inherit, grant, grantOwn, revoke, OVERRIDE_STATES };
    },
    template: `
      <div style="display:flex;flex-direction:column;gap:10px;font:11px/1.2 sans-serif;color:var(--r-color-fg-muted)">
        <RCheckbox v-model:state-value="inherit" :states="OVERRIDE_STATES" label="inherit — defer to group" />
        <RCheckbox v-model:state-value="grant" :states="OVERRIDE_STATES" label="grant — force allow (primary)" />
        <RCheckbox v-model:state-value="grantOwn" :states="OVERRIDE_STATES" label="grant-own — allow own items (accent)" />
        <RCheckbox v-model:state-value="revoke" :states="OVERRIDE_STATES" label="revoke — force deny (danger)" />
      </div>
    `,
  }),
};

// ── Sizes ───────────────────────────────────────────────────────────

export const SizeLadder: Story = {
  name: "Size ladder (xs / sm / md / lg)",
  render: () => ({
    components: { RCheckbox },
    setup: () => {
      const xs = ref(true);
      const sm = ref(true);
      const md = ref(true);
      const lg = ref(true);
      return { xs, sm, md, lg };
    },
    template: `
      <div style="display:flex;flex-direction:column;gap:10px;font:11px/1.2 sans-serif;color:var(--r-color-fg-muted)">
        <RCheckbox v-model="xs" size="xs" label="xs — 12 px" />
        <RCheckbox v-model="sm" size="sm" label="sm — 16 px" />
        <RCheckbox v-model="md" size="md" label="md — 18 px (default)" />
        <RCheckbox v-model="lg" size="lg" label="lg — 22 px" />
      </div>
    `,
  }),
};

// ── Shapes ──────────────────────────────────────────────────────────

export const ShapeLadder: Story = {
  name: "Shape ladder (square / rounded / circle)",
  render: () => ({
    components: { RCheckbox },
    setup: () => {
      const a = ref(true);
      const b = ref(true);
      const c = ref(true);
      return { a, b, c };
    },
    template: `
      <div style="display:flex;flex-direction:column;gap:10px;font:11px/1.2 sans-serif;color:var(--r-color-fg-muted)">
        <RCheckbox v-model="a" shape="square" label="square (default · 4 px radius)" />
        <RCheckbox v-model="b" shape="rounded" label="rounded (8 px radius)" />
        <RCheckbox v-model="c" shape="circle" label="circle (50% — radio-button look)" />
      </div>
    `,
  }),
};

// ── Colors ──────────────────────────────────────────────────────────

export const ColorLadder: Story = {
  name: "Color ladder",
  render: () => ({
    components: { RCheckbox },
    setup: () => {
      const states = ref([
        { color: "primary", label: "primary (default)", checked: true },
        { color: "secondary", label: "secondary", checked: true },
        { color: "accent", label: "accent", checked: true },
        { color: "success", label: "success", checked: true },
        { color: "warning", label: "warning", checked: true },
        { color: "danger", label: "danger", checked: true },
        { color: "info", label: "info", checked: true },
        { color: "romm-gold", label: "romm-gold (legacy)", checked: true },
      ]);
      return { states };
    },
    template: `
      <div style="display:flex;flex-direction:column;gap:10px">
        <RCheckbox
          v-for="s in states"
          :key="s.color"
          v-model="s.checked"
          :color="s.color"
          :label="s.label"
        />
      </div>
    `,
  }),
};

// ── States ──────────────────────────────────────────────────────────

export const Disabled: Story = {
  args: { label: "Disabled checkbox", disabled: true },
};

export const DisabledChecked: Story = {
  args: { label: "Disabled and checked", disabled: true },
  render: (args) => ({
    components: { RCheckbox },
    setup: () => {
      const value = ref(true);
      return { args, value };
    },
    template: `<RCheckbox v-model="value" v-bind="args" />`,
  }),
};

export const Error: Story = {
  args: { label: "I agree to the terms" },
  render: (args) => ({
    components: { RCheckbox },
    setup: () => {
      const value = ref(false);
      return { args, value };
    },
    template: `<RCheckbox v-model="value" v-bind="args" :error="true" error-messages="This field is required" />`,
  }),
};

// ── Subtitle ────────────────────────────────────────────────────────

export const WithSubtitle: Story = {
  name: "With subtitle",
  args: {
    label: "Send weekly digest",
    subtitle: "We'll email you a Friday recap of new ROMs and scans.",
  },
  render: (args) => ({
    components: { RCheckbox },
    setup: () => {
      const value = ref(false);
      return { args, value };
    },
    template: `<RCheckbox v-model="value" v-bind="args" />`,
  }),
};

// ── Card variant ────────────────────────────────────────────────────

export const CardVariant: Story = {
  name: "Card variant",
  render: () => ({
    components: { RCheckbox },
    setup: () => {
      const a = ref(true);
      const b = ref(false);
      const c = ref(false);
      return { a, b, c };
    },
    template: `
      <div style="display:flex;flex-direction:column;gap:10px;width:360px">
        <RCheckbox
          v-model="a"
          variant="card"
          label="Copy token to clipboard"
          subtitle="Shown once — keep it safe."
        />
        <RCheckbox
          v-model="b"
          variant="card"
          label="Pair device"
          subtitle="Scan a QR code with your phone."
        />
        <RCheckbox
          v-model="c"
          variant="card"
          label="Email me the link"
          subtitle="Sent to your registered address."
        />
      </div>
    `,
  }),
};

export const CardVariantColored: Story = {
  name: "Card variant · success tone",
  render: () => ({
    components: { RCheckbox },
    setup: () => {
      const a = ref(true);
      const b = ref(false);
      return { a, b };
    },
    template: `
      <div style="display:flex;flex-direction:column;gap:10px;width:360px">
        <RCheckbox
          v-model="a"
          variant="card"
          color="success"
          label="Verified email"
          subtitle="Required to recover your account."
        />
        <RCheckbox
          v-model="b"
          variant="card"
          color="success"
          label="Two-factor enabled"
          subtitle="Adds a one-time code at sign-in."
        />
      </div>
    `,
  }),
};

// ── Bare ────────────────────────────────────────────────────────────

// `bare` strips the row's vertical breathing padding and the box↔label
// gap. The box stays the same; only the surrounding chrome is removed.
// Used when the consumer owns the layout (overlay corners, list-row
// columns, dense table cells) and wants the checkbox to sit flush.
export const Bare: Story = {
  name: "Bare (no breathing padding)",
  render: () => ({
    components: { RCheckbox },
    setup: () => {
      const normal = ref(true);
      const bare = ref(true);
      return { normal, bare };
    },
    template: `
      <div style="display:flex;gap:24px;align-items:flex-start;font:11px/1.2 sans-serif;color:var(--r-color-fg-muted)">
        <div style="display:flex;flex-direction:column;gap:8px;padding:12px;border:1px dashed var(--r-color-border);border-radius:6px">
          <span>default (with padding)</span>
          <RCheckbox v-model="normal" label="Default row" />
        </div>
        <div style="display:flex;flex-direction:column;gap:8px;padding:12px;border:1px dashed var(--r-color-border);border-radius:6px">
          <span>bare (flush)</span>
          <RCheckbox v-model="bare" bare label="Bare row" />
        </div>
      </div>
    `,
  }),
  parameters: {
    docs: {
      description: {
        story:
          "Use `bare` when the consumer owns the surrounding layout (e.g. GameCard overlay corner, list-row checkbox column).",
      },
    },
  },
};

// ── Motion ──────────────────────────────────────────────────────────

export const Toggle: Story = {
  name: "Toggle animation",
  render: () => ({
    components: { RCheckbox },
    setup: () => {
      const value = ref(false);
      return { value };
    },
    template: `
      <div style="display:flex;flex-direction:column;align-items:flex-start;gap:14px;font:12px/1.4 sans-serif;color:var(--r-color-fg-muted)">
        <RCheckbox v-model="value" label="Click me — watch the glyph spring in" />
        <span>The check icon scales 0 → 1 with the same RSwitch overshoot easing.</span>
      </div>
    `,
  }),
};

// ── Group ───────────────────────────────────────────────────────────

export const Group: Story = {
  render: () => ({
    components: { RCheckbox },
    setup: () => {
      const a = ref(true);
      const b = ref(false);
      const c = ref(false);
      return { a, b, c };
    },
    template: `
      <div style="display:flex;flex-direction:column;gap:4px">
        <RCheckbox v-model="a" label="Option A" hide-details />
        <RCheckbox v-model="b" label="Option B" hide-details />
        <RCheckbox v-model="c" label="Option C (longer label that wraps to test alignment)" hide-details />
      </div>
    `,
  }),
};

// ── Real-world — "select all" indeterminate ─────────────────────────

export const SelectAll: Story = {
  name: "Select-all (indeterminate header)",
  render: () => ({
    components: { RCheckbox },
    setup() {
      const items = ref([
        { id: 1, name: "platforms.read", checked: true },
        { id: 2, name: "platforms.write", checked: false },
        { id: 3, name: "roms.read", checked: true },
        { id: 4, name: "roms.write", checked: false },
        { id: 5, name: "users.read", checked: false },
      ]);

      const allChecked = computed(() => items.value.every((i) => i.checked));
      const anyChecked = computed(() => items.value.some((i) => i.checked));
      const headerIndeterminate = computed(
        () => anyChecked.value && !allChecked.value,
      );

      function toggleAll(v: boolean) {
        items.value.forEach((i) => {
          i.checked = v;
        });
      }

      return { items, allChecked, headerIndeterminate, toggleAll };
    },
    template: `
      <div style="display:flex;flex-direction:column;gap:8px;width:320px;padding:16px;background:var(--r-color-bg-elevated);border:1px solid var(--r-color-border);border-radius:10px">
        <RCheckbox
          :model-value="allChecked"
          :indeterminate="headerIndeterminate"
          label="Select all scopes"
          hide-details
          @update:model-value="toggleAll"
        />
        <div style="height:1px;background:var(--r-color-border);margin:4px 0"></div>
        <RCheckbox
          v-for="item in items"
          :key="item.id"
          v-model="item.checked"
          :label="item.name"
          hide-details
        />
      </div>
    `,
  }),
};
