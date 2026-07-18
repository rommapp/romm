import type { Meta, StoryObj } from "@storybook/vue3-vite";
import RCard from "./RCard.vue";

const meta: Meta<typeof RCard> = {
  title: "Primitives/RCard",
  component: RCard,
  argTypes: {
    variant: {
      control: "select",
      options: ["flat", "elevated", "translucent", "outlined", "text", "plain"],
    },
    color: { control: "text" },
    elevation: { control: "number" },
    rounded: { control: "text" },
    title: { control: "text" },
    subtitle: { control: "text" },
    loading: { control: "boolean" },
  },
};

export default meta;

type Story = StoryObj<typeof RCard>;

// ── Defaults ────────────────────────────────────────────────────────

export const Default: Story = {
  render: (args) => ({
    components: { RCard },
    setup: () => ({ args }),
    template: `
      <RCard v-bind="args" style="width: 360px; padding: var(--r-space-5);">
        Content goes here. RCard has a muted border and an elevated
        background from the v2 tokens.
      </RCard>
    `,
  }),
};

export const WithTitle: Story = {
  args: { title: "Recent scans", subtitle: "Last 24 hours" },
  render: (args) => ({
    components: { RCard },
    setup: () => ({ args }),
    template: `
      <RCard v-bind="args" style="width: 360px;">
        <div style="padding: 12px 20px 18px; color: var(--r-color-fg-muted); font: 13px/1.4 sans-serif;">
          3 platforms scanned · 18 new ROMs · 4 missing.
        </div>
      </RCard>
    `,
  }),
};

// ── Variants ────────────────────────────────────────────────────────

export const Variants: Story = {
  render: () => ({
    components: { RCard },
    template: `
      <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:16px;width:720px">
        <RCard variant="flat" style="padding:18px"><strong>flat</strong> · default surface + border</RCard>
        <RCard variant="elevated" style="padding:18px"><strong>elevated</strong> · surface + shadow</RCard>
        <RCard variant="translucent" color="primary" style="padding:18px"><strong>translucent</strong> · tinted</RCard>
        <RCard variant="outlined" style="padding:18px"><strong>outlined</strong> · border-only</RCard>
        <RCard variant="text" color="primary" style="padding:18px"><strong>text</strong> · just coloured text</RCard>
        <RCard variant="plain" style="padding:18px"><strong>plain</strong> · zero chrome</RCard>
      </div>
    `,
  }),
};

// ── Tones ───────────────────────────────────────────────────────────

export const Tones: Story = {
  name: "Tones · translucent",
  render: () => ({
    components: { RCard },
    template: `
      <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px;width:720px">
        <RCard variant="translucent" color="primary" style="padding:14px">primary</RCard>
        <RCard variant="translucent" color="secondary" style="padding:14px">secondary</RCard>
        <RCard variant="translucent" color="accent" style="padding:14px">accent</RCard>
        <RCard variant="translucent" color="success" style="padding:14px">success</RCard>
        <RCard variant="translucent" color="warning" style="padding:14px">warning</RCard>
        <RCard variant="translucent" color="danger" style="padding:14px">danger</RCard>
        <RCard variant="translucent" color="info" style="padding:14px">info</RCard>
        <RCard variant="translucent" style="padding:14px">neutral</RCard>
      </div>
    `,
  }),
};

// ── Elevation ───────────────────────────────────────────────────────

export const ElevationLadder: Story = {
  name: "Elevation ladder",
  render: () => ({
    components: { RCard },
    template: `
      <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:36px;width:720px;padding:24px;font:11px/1.2 sans-serif;color:var(--r-color-fg-muted)">
        <div style="display:flex;flex-direction:column;align-items:center;gap:10px">
          <RCard variant="elevated" :elevation="0" style="width:160px;padding:18px">e=0</RCard>
          <span>0 (none)</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:10px">
          <RCard variant="elevated" :elevation="1" style="width:160px;padding:18px">e=1</RCard>
          <span>1</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:10px">
          <RCard variant="elevated" :elevation="2" style="width:160px;padding:18px">e=2</RCard>
          <span>2</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:10px">
          <RCard variant="elevated" :elevation="4" style="width:160px;padding:18px">e=4</RCard>
          <span>4</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:10px">
          <RCard variant="elevated" :elevation="8" style="width:160px;padding:18px">e=8</RCard>
          <span>8</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:10px">
          <RCard variant="elevated" :elevation="16" style="width:160px;padding:18px">e=16</RCard>
          <span>16</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:10px">
          <RCard variant="elevated" :elevation="24" style="width:160px;padding:18px">e=24</RCard>
          <span>24</span>
        </div>
      </div>
    `,
  }),
};

// ── Rounded ─────────────────────────────────────────────────────────

export const RoundedLadder: Story = {
  name: "Rounded ladder",
  render: () => ({
    components: { RCard },
    template: `
      <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:16px;width:720px;font:11px/1.2 sans-serif;color:var(--r-color-fg-muted)">
        <div style="display:flex;flex-direction:column;align-items:center;gap:8px">
          <RCard :rounded="0" style="width:160px;padding:18px">rounded 0</RCard>
          <span>0</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:8px">
          <RCard rounded="sm" style="width:160px;padding:18px">rounded sm</RCard>
          <span>sm · 4</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:8px">
          <RCard rounded="md" style="width:160px;padding:18px">rounded md</RCard>
          <span>md · 8</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:8px">
          <RCard rounded="lg" style="width:160px;padding:18px">rounded lg</RCard>
          <span>lg · 12 (default)</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:8px">
          <RCard rounded="xl" style="width:160px;padding:18px">rounded xl</RCard>
          <span>xl · 16</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:8px">
          <RCard :rounded="24" style="width:160px;padding:18px">rounded 24</RCard>
          <span>24px</span>
        </div>
      </div>
    `,
  }),
};

// ── Loading ─────────────────────────────────────────────────────────

export const Loading: Story = {
  name: "Loading bar",
  render: () => ({
    components: { RCard },
    template: `
      <div style="display:flex;flex-direction:column;gap:18px;width:360px">
        <RCard loading title="Fetching metadata" subtitle="Connecting to IGDB…">
          <div style="padding:8px 20px 18px;color:var(--r-color-fg-muted);font:12px/1.4 sans-serif">
            Card content stays visible while the bar slides at the top.
          </div>
        </RCard>
        <RCard loading variant="elevated" :elevation="4" color="primary">
          <div style="padding:18px 20px;font:12px/1.4 sans-serif">
            Loading bar adapts to the card's tone (uses <code>--r-card-color</code> when present).
          </div>
        </RCard>
      </div>
    `,
  }),
};

// ── Real-world ──────────────────────────────────────────────────────

export const AuthCardSim: Story = {
  name: "AuthCard reproduction",
  render: () => ({
    components: { RCard },
    template: `
      <RCard variant="elevated" :elevation="4" style="width:320px">
        <div style="display:flex;flex-direction:column;align-items:center;gap:18px;padding:24px">
          <div style="width:80px;height:80px;border-radius:18px;background:var(--r-color-brand-primary);display:flex;align-items:center;justify-content:center;color:white;font:700 22px/1 sans-serif">R</div>
          <h2 style="margin:0;font:600 18px/1.2 sans-serif">Welcome back</h2>
          <p style="margin:0;color:var(--r-color-fg-muted);font:13px/1.4 sans-serif;text-align:center">Sign in to your RomM library</p>
        </div>
      </RCard>
    `,
  }),
};

export const SettingsPanel: Story = {
  name: "Settings panel (Player usage)",
  render: () => ({
    components: { RCard },
    template: `
      <RCard variant="flat" style="width:320px">
        <div style="display:flex;align-items:center;gap:8px;padding:12px 16px;color:var(--r-color-fg-muted);font:11px/1 sans-serif;font-weight:700;letter-spacing:0.06em;text-transform:uppercase;border-bottom:1px solid var(--r-color-border)">
          Settings
        </div>
        <div style="padding:14px 16px;font:13px/1.5 sans-serif;color:var(--r-color-fg)">
          <div style="margin-bottom:6px;color:var(--r-color-fg-muted)">Background color</div>
          <div style="display:flex;gap:8px">
            <div style="width:28px;height:28px;border-radius:6px;background:var(--r-color-brand-primary);cursor:pointer"></div>
            <div style="width:28px;height:28px;border-radius:6px;background:var(--r-color-success);cursor:pointer"></div>
            <div style="width:28px;height:28px;border-radius:6px;background:var(--r-color-warning);cursor:pointer"></div>
            <div style="width:28px;height:28px;border-radius:6px;background:var(--r-color-danger);cursor:pointer"></div>
          </div>
        </div>
      </RCard>
    `,
  }),
};
