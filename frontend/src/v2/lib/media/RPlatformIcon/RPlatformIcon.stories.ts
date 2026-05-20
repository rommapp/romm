import type { Meta, StoryObj } from "@storybook/vue3-vite";
import RPlatformIcon from "./RPlatformIcon.vue";

const meta: Meta<typeof RPlatformIcon> = {
  title: "Media/RPlatformIcon",
  component: RPlatformIcon,
  argTypes: {
    name: { control: "text" },
    src: { control: "text" },
    size: { control: "number" },
    title: { control: "text" },
    showTooltip: { control: "boolean" },
  },
};

export default meta;

type Story = StoryObj<typeof RPlatformIcon>;

export const Known: Story = { args: { name: "snes", size: 40 } };
export const Unknown: Story = { args: { name: "does-not-exist", size: 40 } };
export const Row: Story = {
  render: () => ({
    components: { RPlatformIcon },
    template: `
      <div style="display:flex;gap:.5rem;align-items:center">
        <RPlatformIcon name="snes" />
        <RPlatformIcon name="nes" />
        <RPlatformIcon name="gba" />
        <RPlatformIcon name="ps1" />
        <RPlatformIcon name="mystery" />
      </div>
    `,
  }),
};

// Size ladder — `size` binds directly to width/height inline so the
// icon honours the requested dimension even inside indefinite flex
// parents (e.g. RBtn's icon slot). Previously the icon was clamped
// by `max-width: 100% / max-height: 100%` to whatever the parent
// gave it, which silently shrunk it when the parent had no defined
// extent. The badge in GameCard relies on this fix.
export const SizeLadder: Story = {
  name: "Size ladder",
  render: () => ({
    components: { RPlatformIcon },
    template: `
      <div style="display:flex;gap:14px;align-items:center;font:11px/1.2 sans-serif;color:var(--r-color-fg-muted)">
        <div style="display:flex;flex-direction:column;align-items:center;gap:4px">
          <RPlatformIcon name="snes" :size="16" />
          <span>16</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:4px">
          <RPlatformIcon name="snes" :size="22" />
          <span>22</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:4px">
          <RPlatformIcon name="snes" :size="32" />
          <span>32</span>
        </div>
        <div style="display:flex;flex-direction:column;align-items:center;gap:4px">
          <RPlatformIcon name="snes" :size="48" />
          <span>48</span>
        </div>
      </div>
    `,
  }),
  parameters: {
    docs: {
      description: {
        story:
          "`size` is bound to inline `width`/`height` and does not clamp to the parent — useful when the icon sits inside an indefinite-extent flex slot.",
      },
    },
  },
};

// Inside an indefinite flex container — proves the size prop is
// honoured even when the parent has no defined cross-axis extent.
// Regression guard for the GameCard platform badge.
export const InsideFlexParent: Story = {
  name: "Inside indefinite-extent flex parent",
  render: () => ({
    components: { RPlatformIcon },
    template: `
      <div style="display:flex;align-items:center;gap:6px;padding:6px;border:1px dashed var(--r-color-border);border-radius:6px">
        <span style="font:11px sans-serif;color:var(--r-color-fg-muted)">indefinite flex parent →</span>
        <RPlatformIcon name="snes" :size="22" />
      </div>
    `,
  }),
};
