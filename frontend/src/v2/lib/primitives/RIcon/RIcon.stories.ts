import type { Meta, StoryObj } from "@storybook/vue3-vite";
import "./RIcon.stories.css";
import RIcon from "./RIcon.vue";

const meta: Meta<typeof RIcon> = {
  title: "Primitives/RIcon",
  component: RIcon,
  argTypes: {
    icon: { control: "text" },
    size: { control: "text" },
    color: { control: "text" },
  },
};

export default meta;

type Story = StoryObj<typeof RIcon>;

export const Default: Story = {
  args: { icon: "mdi-controller" },
};

// ── Sizes ────────────────────────────────────────────────────────────

export const SizeLadder: Story = {
  name: "Size ladder",
  render: () => ({
    components: { RIcon },
    template: `
      <div style="display:flex;align-items:flex-end;gap:24px">
        <div style="display:flex;flex-direction:column;align-items:center;gap:6px;font:11px/1.2 sans-serif;color:var(--r-color-fg-muted)">
          <RIcon icon="mdi-star" size="x-small" />
          <span>x-small · 12px</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:6px;font:11px/1.2 sans-serif;color:var(--r-color-fg-muted)">
          <RIcon icon="mdi-star" size="small" />
          <span>small · 16px</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:6px;font:11px/1.2 sans-serif;color:var(--r-color-fg-muted)">
          <RIcon icon="mdi-star" size="default" />
          <span>default · 24px</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:6px;font:11px/1.2 sans-serif;color:var(--r-color-fg-muted)">
          <RIcon icon="mdi-star" size="large" />
          <span>large · 36px</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:6px;font:11px/1.2 sans-serif;color:var(--r-color-fg-muted)">
          <RIcon icon="mdi-star" size="x-large" />
          <span>x-large · 40px</span>
        </div>
      </div>
    `,
  }),
};

export const NumericSizes: Story = {
  name: "Numeric sizes",
  render: () => ({
    components: { RIcon },
    template: `
      <div style="display:flex;align-items:flex-end;gap:24px">
        <div style="display:flex;flex-direction:column;align-items:center;gap:6px;font:11px/1.2 sans-serif;color:var(--r-color-fg-muted)">
          <RIcon icon="mdi-controller" :size="14" />
          <span>14</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:6px;font:11px/1.2 sans-serif;color:var(--r-color-fg-muted)">
          <RIcon icon="mdi-controller" :size="20" />
          <span>20</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:6px;font:11px/1.2 sans-serif;color:var(--r-color-fg-muted)">
          <RIcon icon="mdi-controller" :size="28" />
          <span>28</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:6px;font:11px/1.2 sans-serif;color:var(--r-color-fg-muted)">
          <RIcon icon="mdi-controller" :size="48" />
          <span>48</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:6px;font:11px/1.2 sans-serif;color:var(--r-color-fg-muted)">
          <RIcon icon="mdi-controller" size="64px" />
          <span>"64px"</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:6px;font:11px/1.2 sans-serif;color:var(--r-color-fg-muted)">
          <RIcon icon="mdi-controller" size="2em" />
          <span>"2em"</span>
        </div>
      </div>
    `,
  }),
};

// ── Colours ──────────────────────────────────────────────────────────

export const Tones: Story = {
  render: () => ({
    components: { RIcon },
    template: `
      <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:16px 24px;font:11px/1.2 sans-serif;color:var(--r-color-fg-muted)">
        <div style="display:flex;flex-direction:column;align-items:center;gap:6px">
          <RIcon icon="mdi-circle" color="primary" size="32" />
          <span>primary</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:6px">
          <RIcon icon="mdi-circle" color="secondary" size="32" />
          <span>secondary</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:6px">
          <RIcon icon="mdi-circle" color="accent" size="32" />
          <span>accent</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:6px">
          <RIcon icon="mdi-check-circle" color="success" size="32" />
          <span>success</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:6px">
          <RIcon icon="mdi-alert" color="warning" size="32" />
          <span>warning</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:6px">
          <RIcon icon="mdi-close-circle" color="danger" size="32" />
          <span>danger</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:6px">
          <RIcon icon="mdi-information" color="info" size="32" />
          <span>info</span>
        </div>
      </div>
    `,
  }),
};

export const LegacyColors: Story = {
  name: "Legacy romm-* colours",
  render: () => ({
    components: { RIcon },
    template: `
      <div style="display:flex;gap:24px;font:11px/1.2 sans-serif;color:var(--r-color-fg-muted)">
        <div style="display:flex;flex-direction:column;align-items:center;gap:6px">
          <RIcon icon="mdi-heart" color="romm-red" size="32" />
          <span>romm-red</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:6px">
          <RIcon icon="mdi-leaf" color="romm-green" size="32" />
          <span>romm-green</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:6px">
          <RIcon icon="mdi-water" color="romm-blue" size="32" />
          <span>romm-blue</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:6px">
          <RIcon icon="mdi-star" color="romm-gold" size="32" />
          <span>romm-gold</span>
        </div>
      </div>
    `,
  }),
};

export const PassThrough: Story = {
  name: "CSS-colour pass-through",
  render: () => ({
    components: { RIcon },
    template: `
      <div style="display:flex;gap:24px;font:11px/1.2 sans-serif;color:var(--r-color-fg-muted)">
        <div style="display:flex;flex-direction:column;align-items:center;gap:6px">
          <RIcon icon="mdi-square" color="#ff00ff" size="32" />
          <code>#ff00ff</code>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:6px">
          <RIcon icon="mdi-square" color="rgb(80, 200, 220)" size="32" />
          <code>rgb(...)</code>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:6px">
          <RIcon icon="mdi-square" color="tomato" size="32" />
          <code>tomato</code>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:6px">
          <RIcon icon="mdi-square" color="hsl(280, 70%, 60%)" size="32" />
          <code>hsl(...)</code>
        </div>
      </div>
    `,
  }),
};

// ── Composition & inheritance ────────────────────────────────────────

export const InheritColor: Story = {
  name: "Inherits parent colour",
  render: () => ({
    components: { RIcon },
    template: `
      <div style="display:flex;flex-direction:column;gap:14px;font:13px/1.4 sans-serif">
        <div style="color:var(--r-color-brand-primary);display:flex;align-items:center;gap:8px">
          <RIcon icon="mdi-information" />
          <span>Wrapped in brand-primary text — icon follows.</span>
        </div>
        <div style="color:var(--r-color-danger);display:flex;align-items:center;gap:8px">
          <RIcon icon="mdi-alert-octagon" />
          <span>Wrapped in danger text — icon follows.</span>
        </div>
        <div style="color:var(--r-color-fg-muted);display:flex;align-items:center;gap:8px">
          <RIcon icon="mdi-help-circle" />
          <span>Muted parent — muted icon.</span>
        </div>
      </div>
    `,
  }),
};

export const WithText: Story = {
  name: "Inline with text",
  render: () => ({
    components: { RIcon },
    template: `
      <div style="display:flex;flex-direction:column;gap:10px;font:14px/1.4 sans-serif;color:var(--r-color-fg)">
        <div style="display:inline-flex;align-items:center;gap:6px">
          <RIcon icon="mdi-clock-outline" size="16" />
          Last played 2 hours ago
        </div>
        <div style="display:inline-flex;align-items:center;gap:6px">
          <RIcon icon="mdi-content-save-outline" size="16" color="success" />
          Saved successfully
        </div>
        <div style="display:inline-flex;align-items:center;gap:6px">
          <RIcon icon="mdi-trash-can-outline" size="16" color="danger" />
          Delete this collection
        </div>
        <h2 style="display:inline-flex;align-items:center;gap:10px;margin:0">
          <RIcon icon="mdi-gamepad-variant" size="28" color="primary" />
          Library
        </h2>
      </div>
    `,
  }),
};

// ── Motion demos ─────────────────────────────────────────────────────

export const Spinning: Story = {
  name: "Spinning (mdi-spin)",
  render: () => ({
    components: { RIcon },
    template: `
      <div style="display:flex;align-items:center;gap:24px;font:12px/1.2 sans-serif;color:var(--r-color-fg-muted)">
        <RIcon icon="mdi-loading" size="32" color="primary" class="mdi-spin" />
        <RIcon icon="mdi-refresh" size="32" color="info" class="mdi-spin" />
        <RIcon icon="mdi-progress-helper" size="32" color="accent" class="mdi-spin" />
        <span>Built-in <code>mdi-spin</code> from <code>@mdi/font</code> composes with the base — no spin prop needed.</span>
      </div>
    `,
  }),
};

export const ColorSwap: Story = {
  name: "Hover colour swap (motion preview)",
  render: () => ({
    components: { RIcon },
    template: `
      <div style="display:flex;gap:24px;align-items:center;font:12px/1.2 sans-serif;color:var(--r-color-fg-muted)">
        <RIcon icon="mdi-heart" size="32" class="r-icon-story-swap" />
        <RIcon icon="mdi-star" size="32" class="r-icon-story-swap--fav" />
        <RIcon icon="mdi-trash-can-outline" size="32" class="r-icon-story-swap--del" />
        <span>Hover — icon transitions colour + transform smoothly.</span>
      </div>
    `,
  }),
};

// ── Catch-all ────────────────────────────────────────────────────────

export const Gallery: Story = {
  render: () => ({
    components: { RIcon },
    template: `
      <div style="display:flex;flex-wrap:wrap;gap:24px;align-items:center">
        <RIcon icon="mdi-home" />
        <RIcon icon="mdi-controller" color="primary" />
        <RIcon icon="mdi-star" color="romm-gold" size="28" />
        <RIcon icon="mdi-trash-can-outline" color="romm-red" />
        <RIcon icon="mdi-check-circle" color="romm-green" />
        <RIcon icon="mdi-account-circle" color="info" size="32" />
        <RIcon icon="mdi-cog" color="secondary" />
        <RIcon icon="mdi-pulse" color="accent" size="20" />
      </div>
    `,
  }),
};
