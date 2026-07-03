import type { Meta, StoryObj } from "@storybook/vue3-vite";
import { expect, waitFor, within } from "storybook/test";
import { ref } from "vue";
import RBtn from "@/v2/lib/primitives/RBtn/RBtn.vue";
import RIcon from "@/v2/lib/primitives/RIcon/RIcon.vue";
import RTooltip from "./RTooltip.vue";

// Dispatch a pointerenter with an explicit `pointerType` — `userEvent.hover`
// can't set it, and the touch-gating branch keys off exactly that.
function firePointerEnter(el: Element, pointerType: "mouse" | "touch") {
  let ev: Event;
  try {
    ev = new PointerEvent("pointerenter", { bubbles: false, pointerType });
  } catch {
    ev = new Event("pointerenter", { bubbles: false });
  }
  if ((ev as PointerEvent).pointerType !== pointerType) {
    Object.defineProperty(ev, "pointerType", {
      value: pointerType,
      configurable: true,
    });
  }
  el.dispatchEvent(ev);
}

// A tap/click of a given pointer type: pointerdown (so the tooltip can read
// the pointer type) followed by the click.
function fireTap(el: Element, pointerType: "mouse" | "touch") {
  let down: Event;
  try {
    down = new PointerEvent("pointerdown", { bubbles: true, pointerType });
  } catch {
    down = new Event("pointerdown", { bubbles: true });
  }
  if ((down as PointerEvent).pointerType !== pointerType) {
    Object.defineProperty(down, "pointerType", {
      value: pointerType,
      configurable: true,
    });
  }
  el.dispatchEvent(down);
  el.dispatchEvent(new MouseEvent("click", { bubbles: true }));
}

const meta: Meta<typeof RTooltip> = {
  title: "Structural/RTooltip",
  component: RTooltip,
  argTypes: {
    text: { control: "text" },
    location: {
      control: "select",
      options: [
        "top",
        "bottom",
        "start",
        "end",
        "top start",
        "top end",
        "bottom start",
        "bottom end",
      ],
    },
    openDelay: { control: "number" },
    closeDelay: { control: "number" },
    offset: { control: "number" },
    contentClass: { control: "text" },
    disabled: { control: "boolean" },
  },
};

export default meta;

type Story = StoryObj<typeof RTooltip>;

// ── Defaults ────────────────────────────────────────────────────────

export const Default: Story = {
  name: "Default · slot activator",
  args: { text: "Save your progress", location: "top" },
  render: (args) => ({
    components: { RTooltip, RBtn },
    setup: () => ({ args }),
    template: `
      <div style="padding:48px;display:flex;justify-content:center">
        <RTooltip v-bind="args">
          <template #activator="{ props }">
            <RBtn v-bind="props" prepend-icon="mdi-content-save">Save</RBtn>
          </template>
        </RTooltip>
      </div>
    `,
  }),
};

export const ParentAttach: Story = {
  name: "Parent attach (no slot)",
  render: () => ({
    components: { RTooltip, RBtn },
    template: `
      <div style="padding:48px;display:flex;justify-content:center">
        <RBtn icon="mdi-delete" variant="translucent">
          <RTooltip activator="parent" text="Delete this item" location="top" />
        </RBtn>
      </div>
    `,
  }),
};

// ── Placements ──────────────────────────────────────────────────────

export const PlacementCardinals: Story = {
  name: "Placement · cardinals",
  render: () => ({
    components: { RTooltip, RBtn },
    template: `
      <div style="padding:80px;display:flex;gap:24px;flex-wrap:wrap;justify-content:center">
        <RTooltip text="Tooltip on top" location="top">
          <template #activator="{ props }">
            <RBtn v-bind="props" icon="mdi-arrow-up" />
          </template>
        </RTooltip>
        <RTooltip text="Tooltip on end" location="end">
          <template #activator="{ props }">
            <RBtn v-bind="props" icon="mdi-arrow-right" />
          </template>
        </RTooltip>
        <RTooltip text="Tooltip on bottom" location="bottom">
          <template #activator="{ props }">
            <RBtn v-bind="props" icon="mdi-arrow-down" />
          </template>
        </RTooltip>
        <RTooltip text="Tooltip on start" location="start">
          <template #activator="{ props }">
            <RBtn v-bind="props" icon="mdi-arrow-left" />
          </template>
        </RTooltip>
      </div>
    `,
  }),
};

export const PlacementDiagonals: Story = {
  name: "Placement · diagonals",
  render: () => ({
    components: { RTooltip, RBtn },
    template: `
      <div style="padding:80px;display:grid;grid-template-columns:repeat(4,auto);gap:24px;justify-content:center">
        <RTooltip text="top-start" location="top start">
          <template #activator="{ props }">
            <RBtn v-bind="props" size="small">top-start</RBtn>
          </template>
        </RTooltip>
        <RTooltip text="top-end" location="top end">
          <template #activator="{ props }">
            <RBtn v-bind="props" size="small">top-end</RBtn>
          </template>
        </RTooltip>
        <RTooltip text="bottom-start" location="bottom start">
          <template #activator="{ props }">
            <RBtn v-bind="props" size="small">bottom-start</RBtn>
          </template>
        </RTooltip>
        <RTooltip text="bottom-end" location="bottom end">
          <template #activator="{ props }">
            <RBtn v-bind="props" size="small">bottom-end</RBtn>
          </template>
        </RTooltip>
      </div>
    `,
  }),
};

export const FlipNearEdge: Story = {
  name: "Auto-flip near viewport edge",
  render: () => ({
    components: { RTooltip, RBtn },
    template: `
      <div style="height:400px;display:flex;justify-content:space-between;align-items:flex-start;padding:8px">
        <RTooltip text="Asked for 'start' but flips to 'end' near the left edge" location="start">
          <template #activator="{ props }">
            <RBtn v-bind="props" prepend-icon="mdi-arrow-left">Hover me</RBtn>
          </template>
        </RTooltip>
        <RTooltip text="Asked for 'end' but flips to 'start' near the right edge" location="end">
          <template #activator="{ props }">
            <RBtn v-bind="props" prepend-icon="mdi-arrow-right">Hover me</RBtn>
          </template>
        </RTooltip>
      </div>
    `,
  }),
};

// ── Content variants ────────────────────────────────────────────────

export const LongText: Story = {
  name: "Long-form text",
  args: {
    text: "Scans the selected library path, matches any new ROMs against the configured metadata providers, and refreshes artwork for existing entries.",
    location: "top",
  },
  render: (args) => ({
    components: { RTooltip, RBtn },
    setup: () => ({ args }),
    template: `
      <div style="padding:80px;display:flex;justify-content:center">
        <RTooltip v-bind="args">
          <template #activator="{ props }">
            <RBtn v-bind="props" prepend-icon="mdi-refresh">Full scan</RBtn>
          </template>
        </RTooltip>
      </div>
    `,
  }),
};

export const CustomContent: Story = {
  name: "Custom slot content",
  render: () => ({
    components: { RTooltip, RBtn, RIcon },
    template: `
      <div style="padding:80px;display:flex;justify-content:center">
        <RTooltip location="top">
          <template #activator="{ props }">
            <RBtn v-bind="props" icon="mdi-keyboard">Shortcuts</RBtn>
          </template>
          <div style="display:flex;flex-direction:column;gap:4px">
            <div style="display:flex;align-items:center;gap:8px">
              <RIcon icon="mdi-keyboard-space" size="x-small" />
              <span>Open palette</span>
            </div>
            <div style="display:flex;align-items:center;gap:8px;color:var(--r-color-fg-muted)">
              <RIcon icon="mdi-apple-keyboard-command" size="x-small" />
              <span>+ K to focus</span>
            </div>
          </div>
        </RTooltip>
      </div>
    `,
  }),
};

// ── States ──────────────────────────────────────────────────────────

export const Disabled: Story = {
  name: "Disabled (no-op)",
  args: { text: "You shouldn't see me", location: "top", disabled: true },
  render: (args) => ({
    components: { RTooltip, RBtn },
    setup: () => ({ args }),
    template: `
      <div style="padding:48px;display:flex;justify-content:center">
        <RTooltip v-bind="args">
          <template #activator="{ props }">
            <RBtn v-bind="props" variant="translucent">Hover me — nothing happens</RBtn>
          </template>
        </RTooltip>
      </div>
    `,
  }),
};

export const Delays: Story = {
  name: "Open / close delays",
  render: () => ({
    components: { RTooltip, RBtn },
    template: `
      <div style="padding:60px;display:flex;gap:18px;justify-content:center;flex-wrap:wrap">
        <RTooltip text="instant (0 ms)" :open-delay="0" location="top">
          <template #activator="{ props }">
            <RBtn v-bind="props">0 ms</RBtn>
          </template>
        </RTooltip>
        <RTooltip text="default 300 ms" location="top">
          <template #activator="{ props }">
            <RBtn v-bind="props">300 ms</RBtn>
          </template>
        </RTooltip>
        <RTooltip text="slow 800 ms" :open-delay="800" location="top">
          <template #activator="{ props }">
            <RBtn v-bind="props">800 ms</RBtn>
          </template>
        </RTooltip>
        <RTooltip text="sticky close · 600 ms" :close-delay="600" location="top">
          <template #activator="{ props }">
            <RBtn v-bind="props">sticky</RBtn>
          </template>
        </RTooltip>
      </div>
    `,
  }),
};

export const Controlled: Story = {
  name: "Controlled (v-model)",
  render: () => ({
    components: { RTooltip, RBtn },
    setup: () => {
      const open = ref(false);
      return { open };
    },
    template: `
      <div style="padding:60px;display:flex;flex-direction:column;gap:24px;align-items:center">
        <RTooltip v-model="open" text="Toggled by the button below — hover does nothing here." location="top">
          <template #activator="{ props }">
            <RBtn v-bind="props" prepend-icon="mdi-cursor-default-outline">Hover target</RBtn>
          </template>
        </RTooltip>
        <RBtn :variant="open ? 'flat' : 'translucent'" @click="open = !open">
          {{ open ? "Hide tooltip" : "Show tooltip" }}
        </RBtn>
      </div>
    `,
  }),
};

// ── Offset ──────────────────────────────────────────────────────────

export const OffsetLadder: Story = {
  name: "Offset ladder",
  render: () => ({
    components: { RTooltip, RBtn },
    template: `
      <div style="padding:80px;display:flex;gap:18px;justify-content:center;flex-wrap:wrap">
        <RTooltip text="offset 0 (flush)" :offset="0" location="top">
          <template #activator="{ props }">
            <RBtn v-bind="props">0</RBtn>
          </template>
        </RTooltip>
        <RTooltip text="offset 6 (default)" location="top">
          <template #activator="{ props }">
            <RBtn v-bind="props">6</RBtn>
          </template>
        </RTooltip>
        <RTooltip text="offset 14 (loose)" :offset="14" location="top">
          <template #activator="{ props }">
            <RBtn v-bind="props">14</RBtn>
          </template>
        </RTooltip>
      </div>
    `,
  }),
};

// ── Real-world ──────────────────────────────────────────────────────

export const IconBarRealWorld: Story = {
  name: "Icon toolbar (real-world)",
  render: () => ({
    components: { RTooltip, RBtn },
    template: `
      <div style="padding:48px;display:flex;justify-content:center">
        <div style="display:flex;gap:4px;padding:6px;background:var(--r-color-bg-elevated);border:1px solid var(--r-color-border);border-radius:10px">
          <RTooltip text="Filters" location="bottom">
            <template #activator="{ props }">
              <RBtn v-bind="props" icon="mdi-filter" variant="text" />
            </template>
          </RTooltip>
          <RTooltip text="Sort" location="bottom">
            <template #activator="{ props }">
              <RBtn v-bind="props" icon="mdi-sort-variant" variant="text" />
            </template>
          </RTooltip>
          <RTooltip text="Search" location="bottom">
            <template #activator="{ props }">
              <RBtn v-bind="props" icon="mdi-magnify" variant="text" />
            </template>
          </RTooltip>
          <RTooltip text="More actions" location="bottom">
            <template #activator="{ props }">
              <RBtn v-bind="props" icon="mdi-dots-vertical" variant="text" />
            </template>
          </RTooltip>
        </div>
      </div>
    `,
  }),
};

// ── Touch gating (behavioral) ───────────────────────────────────────
// A touch "hover" is really a tap that fires the underlying action, so a
// tooltip there would linger over whatever the tap opened. The tooltip must
// reveal for mouse/pen hover only, and a click must always dismiss it.
export const TouchGating: Story = {
  name: "Touch gating (play)",
  args: { text: "Tooltip body text", location: "top", openDelay: 0 },
  render: (args) => ({
    components: { RTooltip, RBtn },
    setup: () => ({ args }),
    template: `
      <div class="r-v2 r-v2-dark" style="padding:48px;display:flex;justify-content:center;background:#07070f">
        <RTooltip v-bind="args">
          <template #activator="{ props }">
            <RBtn v-bind="props">Hover target</RBtn>
          </template>
        </RTooltip>
      </div>
    `,
  }),
  play: async ({ canvasElement, step }) => {
    const canvas = within(canvasElement);
    // The tooltip teleports to <body>, outside canvasElement.
    const body = within(document.body);
    const activator = canvas.getByRole("button", { name: /hover target/i });

    await step("a touch hover does NOT reveal the tooltip", async () => {
      firePointerEnter(activator, "touch");
      await new Promise((r) => setTimeout(r, 50));
      expect(body.queryByRole("tooltip")).toBeNull();
    });

    await step("a mouse hover reveals it", async () => {
      firePointerEnter(activator, "mouse");
      const tip = await body.findByRole("tooltip");
      expect(tip).toHaveTextContent("Tooltip body text");
    });

    await step("a click dismisses it", async () => {
      activator.dispatchEvent(new MouseEvent("click", { bubbles: true }));
      await waitFor(() => expect(body.queryByRole("tooltip")).toBeNull());
    });
  },
};

// `open-on-tap` — a standalone info affordance that must reveal on touch too
// (tap toggles; a mouse click opens rather than closing a hover-revealed tip).
export const OpenOnTap: Story = {
  name: "Open on tap (play)",
  args: {
    text: "Tooltip body text",
    location: "top",
    openOnTap: true,
    openDelay: 0,
  },
  render: (args) => ({
    components: { RTooltip, RBtn },
    setup: () => ({ args }),
    template: `
      <div class="r-v2 r-v2-dark" style="padding:48px;display:flex;justify-content:center;background:#07070f">
        <RTooltip v-bind="args">
          <template #activator="{ props }">
            <RBtn v-bind="props">Tap target</RBtn>
          </template>
        </RTooltip>
      </div>
    `,
  }),
  play: async ({ canvasElement, step }) => {
    const canvas = within(canvasElement);
    const body = within(document.body);
    const activator = canvas.getByRole("button", { name: /tap target/i });

    await step("a touch tap reveals the tooltip", async () => {
      fireTap(activator, "touch");
      const tip = await body.findByRole("tooltip");
      expect(tip).toHaveTextContent("Tooltip body text");
    });

    await step("a second touch tap toggles it closed", async () => {
      fireTap(activator, "touch");
      await waitFor(() => expect(body.queryByRole("tooltip")).toBeNull());
    });

    await step("a mouse click opens it", async () => {
      fireTap(activator, "mouse");
      expect(await body.findByRole("tooltip")).toBeInTheDocument();
    });

    await step(
      "a second mouse click keeps it open (no toggle-closed)",
      async () => {
        fireTap(activator, "mouse");
        expect(body.queryByRole("tooltip")).not.toBeNull();
      },
    );
  },
};

export const FormHelper: Story = {
  name: "Form-field helper (parent-attach)",
  render: () => ({
    components: { RTooltip },
    template: `
      <div style="padding:32px;display:flex;flex-direction:column;gap:8px;width:320px;margin:0 auto">
        <label style="display:flex;align-items:center;gap:6px;font:12px sans-serif;color:var(--r-color-fg-muted)">
          API token
          <span
            style="display:inline-flex;width:14px;height:14px;align-items:center;justify-content:center;border-radius:50%;border:1px solid var(--r-color-border-strong);color:var(--r-color-fg-muted);font-size:10px;cursor:help"
          >
            ?
            <RTooltip activator="parent" location="top" text="Tokens are shown once at creation — keep yours somewhere safe." />
          </span>
        </label>
        <div style="padding:8px 10px;border:1px solid var(--r-color-border);border-radius:6px;background:var(--r-color-bg-elevated);font:13px/1.4 monospace;color:var(--r-color-fg-muted)">
          xxxxx-xxxxx-xxxxx-xxxxx
        </div>
      </div>
    `,
  }),
};
