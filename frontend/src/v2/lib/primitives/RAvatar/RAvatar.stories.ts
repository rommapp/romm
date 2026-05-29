import type { Meta, StoryObj } from "@storybook/vue3-vite";
import RAvatar from "./RAvatar.vue";

const meta: Meta<typeof RAvatar> = {
  title: "Primitives/RAvatar",
  component: RAvatar,
  argTypes: {
    size: { control: "text" },
    color: { control: "text" },
    image: { control: "text" },
    icon: { control: "text" },
    rounded: { control: "text" },
    variant: {
      control: "select",
      options: ["flat", "elevated", "translucent", "outlined", "text", "plain"],
    },
  },
};

export default meta;

type Story = StoryObj<typeof RAvatar>;

// ── Content modes ───────────────────────────────────────────────────

export const Initial: Story = {
  args: { color: "primary", size: 40 },
  render: (args) => ({
    components: { RAvatar },
    setup: () => ({ args }),
    template: `<RAvatar v-bind="args">YZ</RAvatar>`,
  }),
};

export const Icon: Story = {
  args: { icon: "mdi-account", color: "primary", size: 40 },
};

export const Image: Story = {
  args: { image: "/assets/isotipo.svg", size: 48 },
};

// ── Size ladder ─────────────────────────────────────────────────────

export const SizeLadder: Story = {
  name: "Size ladder",
  render: () => ({
    components: { RAvatar },
    template: `
      <div style="display:flex;align-items:flex-end;gap:24px;font:11px/1.2 sans-serif;color:var(--r-color-fg-muted)">
        <div style="display:flex;flex-direction:column;align-items:center;gap:8px">
          <RAvatar size="x-small" color="primary">A</RAvatar>
          <span>x-small · 24px</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:8px">
          <RAvatar size="small" color="primary">A</RAvatar>
          <span>small · 32px</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:8px">
          <RAvatar size="default" color="primary">A</RAvatar>
          <span>default · 40px</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:8px">
          <RAvatar size="large" color="primary">A</RAvatar>
          <span>large · 48px</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:8px">
          <RAvatar size="x-large" color="primary">A</RAvatar>
          <span>x-large · 56px</span>
        </div>
      </div>
    `,
  }),
};

export const NumericSizes: Story = {
  name: "Numeric sizes",
  render: () => ({
    components: { RAvatar },
    template: `
      <div style="display:flex;align-items:flex-end;gap:24px;font:11px/1.2 sans-serif;color:var(--r-color-fg-muted)">
        <div style="display:flex;flex-direction:column;align-items:center;gap:8px">
          <RAvatar :size="20" color="accent" icon="mdi-account" />
          <span>20</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:8px">
          <RAvatar :size="32" color="accent" icon="mdi-account" />
          <span>32</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:8px">
          <RAvatar :size="64" color="accent" icon="mdi-account" />
          <span>64</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:8px">
          <RAvatar :size="96" color="accent" icon="mdi-account" />
          <span>96</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:8px">
          <RAvatar :size="128" color="accent" icon="mdi-account" />
          <span>128</span>
        </div>
      </div>
    `,
  }),
};

// ── Variants ────────────────────────────────────────────────────────

export const Variants: Story = {
  render: () => ({
    components: { RAvatar },
    template: `
      <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:18px 24px;font:11px/1.2 sans-serif;color:var(--r-color-fg-muted)">
        <div style="display:flex;flex-direction:column;align-items:center;gap:8px">
          <RAvatar variant="flat" color="primary" size="48">YZ</RAvatar>
          <span>flat</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:8px">
          <RAvatar variant="elevated" color="primary" size="48">YZ</RAvatar>
          <span>elevated</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:8px">
          <RAvatar variant="translucent" color="primary" size="48">YZ</RAvatar>
          <span>translucent</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:8px">
          <RAvatar variant="outlined" color="primary" size="48">YZ</RAvatar>
          <span>outlined</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:8px">
          <RAvatar variant="text" color="primary" size="48">YZ</RAvatar>
          <span>text</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:8px">
          <RAvatar variant="plain" color="primary" size="48">YZ</RAvatar>
          <span>plain</span>
        </div>
      </div>
    `,
  }),
};

// ── Tones ───────────────────────────────────────────────────────────

export const Tones: Story = {
  name: "Tones · flat",
  render: () => ({
    components: { RAvatar },
    template: `
      <div style="display:grid;grid-template-columns:repeat(4,auto);gap:16px 18px;align-items:center;font:11px/1.2 sans-serif;color:var(--r-color-fg-muted)">
        <div style="display:flex;flex-direction:column;align-items:center;gap:6px">
          <RAvatar color="primary" size="40" icon="mdi-account" />
          <span>primary</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:6px">
          <RAvatar color="secondary" size="40" icon="mdi-account" />
          <span>secondary</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:6px">
          <RAvatar color="accent" size="40" icon="mdi-account" />
          <span>accent</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:6px">
          <RAvatar color="success" size="40" icon="mdi-check" />
          <span>success</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:6px">
          <RAvatar color="warning" size="40" icon="mdi-alert" />
          <span>warning</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:6px">
          <RAvatar color="danger" size="40" icon="mdi-close" />
          <span>danger</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:6px">
          <RAvatar color="info" size="40" icon="mdi-information" />
          <span>info</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:6px">
          <RAvatar size="40" icon="mdi-account" />
          <span>no colour</span>
        </div>
      </div>
    `,
  }),
};

export const TonesTranslucent: Story = {
  name: "Tones · translucent",
  render: () => ({
    components: { RAvatar },
    template: `
      <div style="display:flex;gap:16px;align-items:center">
        <RAvatar variant="translucent" color="primary" size="40" icon="mdi-account" />
        <RAvatar variant="translucent" color="secondary" size="40" icon="mdi-account" />
        <RAvatar variant="translucent" color="accent" size="40" icon="mdi-account" />
        <RAvatar variant="translucent" color="success" size="40" icon="mdi-check" />
        <RAvatar variant="translucent" color="warning" size="40" icon="mdi-alert" />
        <RAvatar variant="translucent" color="danger" size="40" icon="mdi-close" />
        <RAvatar variant="translucent" color="info" size="40" icon="mdi-information" />
      </div>
    `,
  }),
};

// ── Shapes ──────────────────────────────────────────────────────────

export const Rounded: Story = {
  name: "Rounded ladder",
  render: () => ({
    components: { RAvatar },
    template: `
      <div style="display:flex;align-items:flex-end;gap:24px;font:11px/1.2 sans-serif;color:var(--r-color-fg-muted)">
        <div style="display:flex;flex-direction:column;align-items:center;gap:8px">
          <RAvatar :rounded="false" color="primary" size="48">R</RAvatar>
          <span>false / "0"</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:8px">
          <RAvatar rounded="sm" color="primary" size="48">R</RAvatar>
          <span>sm · 4</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:8px">
          <RAvatar rounded="md" color="primary" size="48">R</RAvatar>
          <span>md · 8</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:8px">
          <RAvatar rounded="lg" color="primary" size="48">R</RAvatar>
          <span>lg · 12</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:8px">
          <RAvatar rounded="xl" color="primary" size="48">R</RAvatar>
          <span>xl · 16</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:8px">
          <RAvatar rounded="circle" color="primary" size="48">R</RAvatar>
          <span>circle (default)</span>
        </div>
      </div>
    `,
  }),
};

// ── Real-world ──────────────────────────────────────────────────────

export const UserRow: Story = {
  name: "Inside a user row",
  render: () => ({
    components: { RAvatar },
    template: `
      <div style="width:340px;background:var(--r-color-bg-elevated);border:1px solid var(--r-color-border);border-radius:12px;overflow:hidden;font:13px/1.4 sans-serif;color:var(--r-color-fg)">
        <div style="display:flex;align-items:center;gap:12px;padding:12px 16px">
          <RAvatar image="/assets/isotipo.svg" size="36" />
          <div style="display:flex;flex-direction:column;gap:2px">
            <span style="font-weight:600">RomM Admin</span>
            <span style="color:var(--r-color-fg-muted);font-size:11px">admin · last seen 3 min ago</span>
          </div>
        </div>
        <div style="display:flex;align-items:center;gap:12px;padding:12px 16px;border-top:1px solid var(--r-color-border)">
          <RAvatar color="accent" size="36">EM</RAvatar>
          <div style="display:flex;flex-direction:column;gap:2px">
            <span style="font-weight:600">Emma</span>
            <span style="color:var(--r-color-fg-muted);font-size:11px">editor</span>
          </div>
        </div>
        <div style="display:flex;align-items:center;gap:12px;padding:12px 16px;border-top:1px solid var(--r-color-border)">
          <RAvatar variant="translucent" color="info" size="36" icon="mdi-account-question" />
          <div style="display:flex;flex-direction:column;gap:2px">
            <span style="font-weight:600">Guest</span>
            <span style="color:var(--r-color-fg-muted);font-size:11px">viewer · pending</span>
          </div>
        </div>
      </div>
    `,
  }),
};

export const StackedGroup: Story = {
  name: "Stacked group (avatar group)",
  render: () => ({
    components: { RAvatar },
    template: `
      <div style="display:flex;align-items:center">
        <RAvatar color="primary" size="36" style="border:2px solid var(--r-color-bg);position:relative;z-index:5">AB</RAvatar>
        <RAvatar color="accent" size="36" style="margin-left:-12px;border:2px solid var(--r-color-bg);position:relative;z-index:4">CD</RAvatar>
        <RAvatar color="success" size="36" style="margin-left:-12px;border:2px solid var(--r-color-bg);position:relative;z-index:3">EF</RAvatar>
        <RAvatar color="warning" size="36" style="margin-left:-12px;border:2px solid var(--r-color-bg);position:relative;z-index:2">GH</RAvatar>
        <RAvatar variant="translucent" color="info" size="36" style="margin-left:-12px;border:2px solid var(--r-color-bg);position:relative;z-index:1">+5</RAvatar>
      </div>
    `,
  }),
};
