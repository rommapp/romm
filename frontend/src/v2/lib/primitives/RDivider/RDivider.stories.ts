import type { Meta, StoryObj } from "@storybook/vue3-vite";
import RDivider from "./RDivider.vue";

const meta: Meta<typeof RDivider> = {
  title: "Primitives/RDivider",
  component: RDivider,
  argTypes: {
    vertical: { control: "boolean" },
    inset: { control: "boolean" },
    thickness: { control: "text" },
  },
  render: (args) => ({
    components: { RDivider },
    setup: () => ({ args }),
    template: `<div style="width:320px"><RDivider v-bind="args" /></div>`,
  }),
};

export default meta;

type Story = StoryObj<typeof RDivider>;

export const Default: Story = {};

// ── Variants ─────────────────────────────────────────────────────────

export const WithText: Story = {
  name: "With text (default slot)",
  render: (args) => ({
    components: { RDivider },
    setup: () => ({ args }),
    template: `
      <div style="width:320px;color:var(--r-color-fg)">
        <RDivider v-bind="args">or</RDivider>
      </div>
    `,
  }),
};

export const Vertical: Story = {
  args: { vertical: true },
  render: (args) => ({
    components: { RDivider },
    setup: () => ({ args }),
    template: `
      <div style="height:60px;display:flex;align-items:center;gap:16px;color:var(--r-color-fg)">
        <span>Left</span>
        <RDivider v-bind="args" />
        <span>Right</span>
      </div>
    `,
  }),
};

export const VerticalWithText: Story = {
  name: "Vertical with text",
  args: { vertical: true },
  render: (args) => ({
    components: { RDivider },
    setup: () => ({ args }),
    template: `
      <div style="height:120px;display:flex;align-items:stretch;gap:16px;color:var(--r-color-fg)">
        <div style="display:flex;align-items:center;padding:0 16px;background:var(--r-color-surface);border-radius:8px">Top</div>
        <RDivider v-bind="args">or</RDivider>
        <div style="display:flex;align-items:center;padding:0 16px;background:var(--r-color-surface);border-radius:8px">Bottom</div>
      </div>
    `,
  }),
};

// ── Thickness ─────────────────────────────────────────────────────────

export const ThicknessLadder: Story = {
  name: "Thickness ladder",
  render: () => ({
    components: { RDivider },
    template: `
      <div style="width:320px;display:flex;flex-direction:column;gap:18px;font:11px/1.2 sans-serif;color:var(--r-color-fg-muted)">
        <div>
          <RDivider :thickness="1" />
          <div style="margin-top:6px">thickness: 1 (default)</div>
        </div>
        <div>
          <RDivider :thickness="2" />
          <div style="margin-top:6px">thickness: 2</div>
        </div>
        <div>
          <RDivider :thickness="4" />
          <div style="margin-top:6px">thickness: 4</div>
        </div>
        <div>
          <RDivider :thickness="8" />
          <div style="margin-top:6px">thickness: 8</div>
        </div>
      </div>
    `,
  }),
};

export const ThicknessWithText: Story = {
  name: "Thickness — with text",
  render: () => ({
    components: { RDivider },
    template: `
      <div style="width:320px;display:flex;flex-direction:column;gap:18px;color:var(--r-color-fg)">
        <RDivider :thickness="1">1px</RDivider>
        <RDivider :thickness="2">2px</RDivider>
        <RDivider :thickness="4">4px</RDivider>
      </div>
    `,
  }),
};

// ── Inset ────────────────────────────────────────────────────────────

export const Inset: Story = {
  args: { inset: true },
  render: (args) => ({
    components: { RDivider },
    setup: () => ({ args }),
    template: `
      <div style="width:320px;background:var(--r-color-surface);border-radius:8px;overflow:hidden;font:13px/1.4 sans-serif;color:var(--r-color-fg)">
        <div style="display:flex;align-items:center;gap:16px;padding:10px 16px">
          <div style="width:40px;height:40px;border-radius:50%;background:var(--r-color-brand-primary)"></div>
          <span>List item one</span>
        </div>
        <RDivider v-bind="args" />
        <div style="display:flex;align-items:center;gap:16px;padding:10px 16px">
          <div style="width:40px;height:40px;border-radius:50%;background:var(--r-color-brand-accent)"></div>
          <span>List item two</span>
        </div>
        <RDivider v-bind="args" />
        <div style="display:flex;align-items:center;gap:16px;padding:10px 16px">
          <div style="width:40px;height:40px;border-radius:50%;background:var(--r-color-success)"></div>
          <span>List item three</span>
        </div>
      </div>
    `,
  }),
};

// ── Real-world examples ─────────────────────────────────────────────

export const InCard: Story = {
  name: "Inside a card (section break)",
  render: () => ({
    components: { RDivider },
    template: `
      <div style="width:360px;background:var(--r-color-bg-elevated);border:1px solid var(--r-color-border);border-radius:12px;overflow:hidden;font:13px/1.4 sans-serif;color:var(--r-color-fg)">
        <div style="padding:14px 16px;font-weight:600">Display preferences</div>
        <RDivider />
        <div style="padding:14px 16px;color:var(--r-color-fg-muted)">Theme, density, boxart style…</div>
        <RDivider />
        <div style="padding:14px 16px;color:var(--r-color-fg-muted)">Show stats summary on home page.</div>
      </div>
    `,
  }),
};

export const ConsumerOverride: Story = {
  name: "Consumer style override (the Login 'or')",
  render: () => ({
    components: { RDivider },
    template: `
      <div style="width:320px;display:flex;flex-direction:column;gap:8px;padding:24px;background:var(--r-color-bg);border-radius:12px">
        <div style="height:40px;background:var(--r-color-surface);border-radius:6px;display:flex;align-items:center;justify-content:center;color:var(--r-color-fg-muted)">Username field</div>
        <div style="height:40px;background:var(--r-color-surface);border-radius:6px;display:flex;align-items:center;justify-content:center;color:var(--r-color-fg-muted)">Password field</div>
        <div style="height:36px;border-radius:6px;background:var(--r-color-brand-primary);color:white;display:flex;align-items:center;justify-content:center;font-weight:600">Sign in</div>
        <RDivider style="margin: 12px 0; color: var(--r-color-fg-muted); font-size: 11px; text-transform: uppercase; letter-spacing: 0.1em;">
          or
        </RDivider>
        <div style="height:36px;border-radius:6px;background:var(--r-color-surface);color:var(--r-color-fg);display:flex;align-items:center;justify-content:center;font-weight:500">Continue with OIDC</div>
      </div>
    `,
  }),
};

export const Toolbar: Story = {
  name: "Vertical inside a toolbar",
  render: () => ({
    components: { RDivider },
    template: `
      <div style="display:inline-flex;align-items:center;gap:8px;padding:6px 10px;background:var(--r-color-surface);border-radius:8px;color:var(--r-color-fg);font:13px/1 sans-serif">
        <span>File</span>
        <RDivider vertical />
        <span>Edit</span>
        <RDivider vertical />
        <span>View</span>
        <RDivider vertical />
        <span>Help</span>
      </div>
    `,
  }),
};
