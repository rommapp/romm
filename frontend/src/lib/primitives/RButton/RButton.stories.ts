import type { Meta, StoryObj } from "@storybook/vue3-vite";
import { expect, userEvent, within } from "storybook/test";
import { ref } from "vue";
import { CONTRAST_TODO_PARAMETERS } from "@/utils/storyA11y";
import RButton from "./RButton.vue";

const meta: Meta<typeof RButton> = {
  title: "Primitives/RButton",
  component: RButton,
  parameters: CONTRAST_TODO_PARAMETERS,
  argTypes: {
    color: { control: "text" },
    size: {
      control: "select",
      options: ["x-small", "small", "default", "large", "x-large"],
    },
    density: {
      control: "select",
      options: ["default", "comfortable", "compact"],
    },
    rounded: { control: "text" },
    type: {
      control: "select",
      options: ["button", "submit", "reset"],
    },
    icon: { control: "text" },
  },
};

export default meta;

type Story = StoryObj<typeof RButton>;

// ── Defaults ────────────────────────────────────────────────────────

export const Default: Story = {
  render: (args) => ({
    components: { RButton },
    setup: () => ({ args }),
    template: `<RButton v-bind="args">Click me</RButton>`,
  }),
};

export const Primary: Story = {
  args: { color: "primary" },
  render: (args) => ({
    components: { RButton },
    setup: () => ({ args }),
    template: `<RButton v-bind="args">Primary action</RButton>`,
  }),
};

// ── Variants ────────────────────────────────────────────────────────

export const Variants: Story = {
  render: () => ({
    components: { RButton },
    template: `
      <div style="display:grid;grid-template-columns:repeat(3,auto);gap:14px 18px;justify-items:start">
        <RButton variant="flat" color="primary">flat</RButton>
        <RButton variant="elevated" color="primary">elevated</RButton>
        <RButton variant="translucent" color="primary">translucent</RButton>
        <RButton variant="outlined" color="primary">outlined</RButton>
        <RButton variant="text" color="primary">text</RButton>
        <RButton variant="plain" color="primary">plain</RButton>
      </div>
    `,
  }),
};

// ── Size ladder ─────────────────────────────────────────────────────

export const SizeLadder: Story = {
  name: "Size ladder",
  render: () => ({
    components: { RButton },
    template: `
      <div style="display:flex;align-items:flex-end;gap:14px">
        <RButton size="x-small" color="primary">x-small</RButton>
        <RButton size="small" color="primary">small</RButton>
        <RButton size="default" color="primary">default</RButton>
        <RButton size="large" color="primary">large</RButton>
        <RButton size="x-large" color="primary">x-large</RButton>
      </div>
    `,
  }),
};

export const Density: Story = {
  name: "Density compression",
  render: () => ({
    components: { RButton },
    template: `
      <div style="display:flex;align-items:center;gap:14px">
        <RButton density="default" color="primary">default</RButton>
        <RButton density="comfortable" color="primary">comfortable</RButton>
        <RButton density="compact" color="primary">compact</RButton>
      </div>
    `,
  }),
};

// ── Tones ───────────────────────────────────────────────────────────

export const Tones: Story = {
  name: "Tones · flat",
  render: () => ({
    components: { RButton },
    template: `
      <div style="display:flex;flex-wrap:wrap;gap:10px">
        <RButton color="primary">primary</RButton>
        <RButton color="secondary">secondary</RButton>
        <RButton color="accent">accent</RButton>
        <RButton color="success">success</RButton>
        <RButton color="warning">warning</RButton>
        <RButton color="danger">danger</RButton>
        <RButton color="info">info</RButton>
        <RButton>neutral</RButton>
      </div>
    `,
  }),
};

export const TonesTranslucent: Story = {
  name: "Tones · translucent",
  render: () => ({
    components: { RButton },
    template: `
      <div style="display:flex;flex-wrap:wrap;gap:10px">
        <RButton variant="translucent" color="primary">primary</RButton>
        <RButton variant="translucent" color="secondary">secondary</RButton>
        <RButton variant="translucent" color="accent">accent</RButton>
        <RButton variant="translucent" color="success">success</RButton>
        <RButton variant="translucent" color="warning">warning</RButton>
        <RButton variant="translucent" color="danger">danger</RButton>
        <RButton variant="translucent" color="info">info</RButton>
      </div>
    `,
  }),
};

// ── Icons ───────────────────────────────────────────────────────────

export const WithIcons: Story = {
  name: "Prepend / append icons",
  render: () => ({
    components: { RButton },
    template: `
      <div style="display:flex;flex-wrap:wrap;gap:10px">
        <RButton color="primary" prepend-icon="mdi-login">Sign in</RButton>
        <RButton color="success" prepend-icon="mdi-content-save">Save</RButton>
        <RButton variant="outlined" append-icon="mdi-open-in-new">Open docs</RButton>
        <RButton variant="translucent" color="primary" prepend-icon="mdi-filter" append-icon="mdi-menu-down">Filter</RButton>
      </div>
    `,
  }),
};

export const IconOnly: Story = {
  name: "Icon-only buttons",
  render: () => ({
    components: { RButton },
    template: `
      <div style="display:flex;align-items:center;gap:10px">
        <RButton icon="mdi-pencil" variant="text" aria-label="Edit" />
        <RButton icon="mdi-delete" variant="text" color="danger" aria-label="Delete" />
        <RButton icon="mdi-heart" variant="translucent" color="primary" aria-label="Favorite" />
        <RButton icon="mdi-refresh" variant="outlined" aria-label="Refresh" />
        <RButton icon="mdi-plus" color="primary" aria-label="Add" />
      </div>
    `,
  }),
};

export const IconSizeLadder: Story = {
  name: "Icon-only · size ladder",
  render: () => ({
    components: { RButton },
    template: `
      <div style="display:flex;align-items:center;gap:10px">
        <RButton icon="mdi-star" size="x-small" color="primary" aria-label="x-small" />
        <RButton icon="mdi-star" size="small" color="primary" aria-label="small" />
        <RButton icon="mdi-star" size="default" color="primary" aria-label="default" />
        <RButton icon="mdi-star" size="large" color="primary" aria-label="large" />
        <RButton icon="mdi-star" size="x-large" color="primary" aria-label="x-large" />
      </div>
    `,
  }),
};

/**
 * When `icon` is a flag, a default slot replaces the glyph (e.g. GameCard's
 * PlatformIcon badge).
 */
export const IconSlotCustom: Story = {
  name: "Icon-mode · custom slot content",
  render: () => ({
    components: { RButton },
    template: `
      <div style="display:flex;align-items:center;gap:10px">
        <RButton icon variant="translucent" color="primary" aria-label="Image button" style="width:auto;min-width:0;padding:3px">
          <img src="https://placehold.co/22x22/A66/fff?text=P" alt="Platform" style="display:block;width:22px;height:22px;border-radius:3px" />
        </RButton>
        <RButton icon variant="text" aria-label="Emoji button" style="width:auto;min-width:0;padding:3px">
          <span style="font-size:18px;line-height:1">🎮</span>
        </RButton>
        <RButton icon variant="outlined" aria-label="Rating 9" style="width:auto;min-width:0;padding:3px 8px">
          <span style="display:inline-flex;align-items:center;gap:4px;font-size:12px">⭐ <span>9</span></span>
        </RButton>
      </div>
    `,
  }),
  parameters: {
    docs: {
      description: {
        story:
          "Pass `icon` as a flag and put custom content in the default slot. RButton renders the content inside `.r-button__icon-slot` with `line-height: 0` so descender gaps from text/icons don't shift the centering.",
      },
    },
  },
};

// ── Rounded ─────────────────────────────────────────────────────────

export const Rounded: Story = {
  name: "Rounded ladder",
  render: () => ({
    components: { RButton },
    template: `
      <div style="display:flex;flex-wrap:wrap;gap:10px;align-items:center">
        <RButton :rounded="0" color="primary">0</RButton>
        <RButton rounded="sm" color="primary">sm</RButton>
        <RButton rounded="md" color="primary">md (default)</RButton>
        <RButton rounded="lg" color="primary">lg</RButton>
        <RButton rounded="xl" color="primary">xl</RButton>
        <RButton rounded="full" color="primary">full / pill</RButton>
      </div>
    `,
  }),
};

// ── Loading ─────────────────────────────────────────────────────────

export const LoadingState: Story = {
  name: "Loading (interactive)",
  render: () => ({
    components: { RButton },
    setup() {
      const loading = ref(false);
      function run() {
        loading.value = true;
        setTimeout(() => {
          loading.value = false;
        }, 1800);
      }
      return { loading, run };
    },
    template: `
      <div style="display:flex;flex-direction:column;gap:14px;align-items:flex-start">
        <RButton color="primary" :loading="loading" prepend-icon="mdi-content-save" @click="run">
          Save changes
        </RButton>
        <RButton variant="outlined" :loading="loading" @click="run">Submit</RButton>
        <span style="font:12px/1.4 sans-serif;color:var(--r-color-fg-muted)">
          Click — spinner appears after the 200ms debounce; layout doesn't shift.
        </span>
      </div>
    `,
  }),
};

// ── Block / disabled ────────────────────────────────────────────────

export const Block: Story = {
  args: { block: true, prependIcon: "mdi-send", color: "primary" },
  render: (args) => ({
    components: { RButton },
    setup: () => ({ args }),
    template: `<div style="width:360px"><RButton v-bind="args">Submit</RButton></div>`,
  }),
};

export const Disabled: Story = {
  render: () => ({
    components: { RButton },
    template: `
      <div style="display:flex;flex-wrap:wrap;gap:10px">
        <RButton disabled>disabled flat</RButton>
        <RButton variant="outlined" disabled>disabled outlined</RButton>
        <RButton variant="translucent" color="primary" disabled>disabled translucent</RButton>
        <RButton variant="text" color="danger" disabled>disabled text</RButton>
        <RButton icon="mdi-delete" variant="text" disabled aria-label="disabled icon" />
      </div>
    `,
  }),
};

// ── Border modifier ─────────────────────────────────────────────────

export const BorderModifier: Story = {
  name: "Border modifier (chip-style activator)",
  render: () => ({
    components: { RButton },
    template: `
      <div style="display:flex;flex-wrap:wrap;gap:10px;align-items:center">
        <RButton variant="translucent" color="primary" border>translucent + border</RButton>
        <RButton variant="text" color="primary" border>text + border</RButton>
        <RButton variant="translucent" color="accent" border rounded="full">activator pill</RButton>
      </div>
    `,
  }),
};

// ── Polymorphic root ────────────────────────────────────────────────

export const AsLink: Story = {
  name: "Polymorphic (href / to)",
  render: () => ({
    components: { RButton },
    template: `
      <div style="display:flex;flex-direction:column;gap:12px;align-items:flex-start">
        <RButton href="https://romm.app" target="_blank" append-icon="mdi-open-in-new" color="primary">
          External link (&lt;a&gt;)
        </RButton>
        <span style="font:12px/1.4 sans-serif;color:var(--r-color-fg-muted)">
          With <code>to</code>, RButton renders <code>&lt;router-link&gt;</code> (invisible in this story without a router, but the prop is accepted).
        </span>
      </div>
    `,
  }),
};

// ── Real-world stacks ───────────────────────────────────────────────

export const Toolbar: Story = {
  name: "Toolbar row",
  render: () => ({
    components: { RButton },
    template: `
      <div style="display:inline-flex;align-items:center;gap:6px;padding:6px 8px;background:var(--r-color-surface);border-radius:10px">
        <RButton icon="mdi-format-bold" variant="text" size="small" aria-label="Bold" />
        <RButton icon="mdi-format-italic" variant="text" size="small" aria-label="Italic" />
        <RButton icon="mdi-format-underline" variant="text" size="small" aria-label="Underline" />
        <span style="width:1px;height:18px;background:var(--r-color-border);margin:0 4px"></span>
        <RButton icon="mdi-format-list-bulleted" variant="text" size="small" aria-label="List" />
        <RButton icon="mdi-format-quote-close" variant="text" size="small" aria-label="Quote" />
        <RButton icon="mdi-link-variant" variant="text" size="small" aria-label="Link" />
      </div>
    `,
  }),
};

export const FormActions: Story = {
  name: "Form actions row",
  render: () => ({
    components: { RButton },
    template: `
      <div style="display:flex;gap:10px;justify-content:flex-end;padding:14px;background:var(--r-color-bg-elevated);border-radius:10px;width:420px">
        <RButton variant="text">Cancel</RButton>
        <RButton variant="outlined">Save draft</RButton>
        <RButton color="primary" prepend-icon="mdi-send">Publish</RButton>
      </div>
    `,
  }),
};

/**
 * `surface` gives an outlined icon-only RButton the same tinted chrome as the
 * `RSegmentedControl` beside it.
 */
export const SurfaceWithSlider: Story = {
  name: "Surface modifier (icon button next to slider)",
  render: () => ({
    components: { RButton },
    template: `
      <div style="display:flex;gap:8px;align-items:center;padding:16px;background:var(--r-color-bg);width:max-content">
        <RButton variant="outlined" surface icon="mdi-filter-variant" rounded="circle" aria-label="Filters" />
        <div style="display:inline-flex;align-items:center;gap:2px;padding:2px;background:var(--r-color-bg-elevated);border:1px solid var(--r-color-border);border-radius:999px;font-size:11px;color:var(--r-color-fg-muted)">
          <span style="padding:4px 10px">Mock slider wrapper for comparison</span>
        </div>
        <RButton variant="outlined" surface icon="mdi-dots-vertical" rounded="circle" aria-label="More" />
      </div>
      <p style="margin:8px 0 0 16px;font:12px monospace;color:var(--r-color-fg-muted);max-width:480px">
        \`surface\` paints --r-color-bg-elevated so the disc-shaped icon
        button reads as a sibling of the segmented slider next to it.
      </p>
    `,
  }),
};

/**
 * Toggle state: `active` drives `aria-pressed` and, while on, paints the
 * translucent tint of `color` (primary when no colour is given).
 */
export const Active: Story = {
  name: "Active (toggle)",
  render: () => ({
    components: { RButton },
    setup: () => ({ shuffle: ref(false), mute: ref(true) }),
    template: `
      <div style="display:flex;gap:8px;align-items:center">
        <RButton variant="text" icon="mdi-shuffle" aria-label="Shuffle" :active="shuffle" @click="shuffle = !shuffle" />
        <RButton variant="text" color="danger" prepend-icon="mdi-volume-off" :active="mute" @click="mute = !mute">Mute</RButton>
        <RButton variant="outlined" active>Always on</RButton>
        <RButton variant="outlined">Not a toggle</RButton>
        <RButton variant="outlined" aria-pressed="true">Manual pressed</RButton>
      </div>
    `,
  }),
  play: async ({ canvasElement, step }) => {
    const canvas = within(canvasElement);
    const shuffle = canvas.getByRole("button", { name: "Shuffle" });

    await step("starts unpressed and toggles on click", async () => {
      await expect(shuffle).toHaveAttribute("aria-pressed", "false");
      await userEvent.click(shuffle);
      await expect(shuffle).toHaveAttribute("aria-pressed", "true");
      await expect(shuffle).toHaveClass("r-button--translucent");
    });

    await step("leaves aria-pressed off buttons without active", async () => {
      const plain = canvas.getByRole("button", { name: "Not a toggle" });
      await expect(plain).not.toHaveAttribute("aria-pressed");
    });

    await step("keeps a caller's own aria-pressed", async () => {
      const manual = canvas.getByRole("button", { name: "Manual pressed" });
      await expect(manual).toHaveAttribute("aria-pressed", "true");
    });
  },
};
