import type { Meta, StoryObj } from "@storybook/vue3-vite";
import { ref } from "vue";
import RBtn from "./RBtn.vue";

const meta: Meta<typeof RBtn> = {
  title: "Primitives/RBtn",
  component: RBtn,
  argTypes: {
    variant: {
      control: "select",
      options: ["flat", "text", "elevated", "translucent", "outlined", "plain"],
    },
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
    loading: { control: "boolean" },
    disabled: { control: "boolean" },
    block: { control: "boolean" },
    border: { control: "boolean" },
    surface: { control: "boolean" },
    prependIcon: { control: "text" },
    appendIcon: { control: "text" },
  },
};

export default meta;

type Story = StoryObj<typeof RBtn>;

// ── Defaults ────────────────────────────────────────────────────────

export const Default: Story = {
  render: (args) => ({
    components: { RBtn },
    setup: () => ({ args }),
    template: `<RBtn v-bind="args">Click me</RBtn>`,
  }),
};

export const Primary: Story = {
  args: { color: "primary" },
  render: (args) => ({
    components: { RBtn },
    setup: () => ({ args }),
    template: `<RBtn v-bind="args">Primary action</RBtn>`,
  }),
};

// ── Variants ────────────────────────────────────────────────────────

export const Variants: Story = {
  render: () => ({
    components: { RBtn },
    template: `
      <div style="display:grid;grid-template-columns:repeat(3,auto);gap:14px 18px;justify-items:start">
        <RBtn variant="flat" color="primary">flat</RBtn>
        <RBtn variant="elevated" color="primary">elevated</RBtn>
        <RBtn variant="translucent" color="primary">translucent</RBtn>
        <RBtn variant="outlined" color="primary">outlined</RBtn>
        <RBtn variant="text" color="primary">text</RBtn>
        <RBtn variant="plain" color="primary">plain</RBtn>
      </div>
    `,
  }),
};

// ── Size ladder ─────────────────────────────────────────────────────

export const SizeLadder: Story = {
  name: "Size ladder",
  render: () => ({
    components: { RBtn },
    template: `
      <div style="display:flex;align-items:flex-end;gap:14px">
        <RBtn size="x-small" color="primary">x-small</RBtn>
        <RBtn size="small" color="primary">small</RBtn>
        <RBtn size="default" color="primary">default</RBtn>
        <RBtn size="large" color="primary">large</RBtn>
        <RBtn size="x-large" color="primary">x-large</RBtn>
      </div>
    `,
  }),
};

export const Density: Story = {
  name: "Density compression",
  render: () => ({
    components: { RBtn },
    template: `
      <div style="display:flex;align-items:center;gap:14px">
        <RBtn density="default" color="primary">default</RBtn>
        <RBtn density="comfortable" color="primary">comfortable</RBtn>
        <RBtn density="compact" color="primary">compact</RBtn>
      </div>
    `,
  }),
};

// ── Tones ───────────────────────────────────────────────────────────

export const Tones: Story = {
  name: "Tones · flat",
  render: () => ({
    components: { RBtn },
    template: `
      <div style="display:flex;flex-wrap:wrap;gap:10px">
        <RBtn color="primary">primary</RBtn>
        <RBtn color="secondary">secondary</RBtn>
        <RBtn color="accent">accent</RBtn>
        <RBtn color="success">success</RBtn>
        <RBtn color="warning">warning</RBtn>
        <RBtn color="danger">danger</RBtn>
        <RBtn color="info">info</RBtn>
        <RBtn>neutral</RBtn>
      </div>
    `,
  }),
};

export const TonesTranslucent: Story = {
  name: "Tones · translucent",
  render: () => ({
    components: { RBtn },
    template: `
      <div style="display:flex;flex-wrap:wrap;gap:10px">
        <RBtn variant="translucent" color="primary">primary</RBtn>
        <RBtn variant="translucent" color="secondary">secondary</RBtn>
        <RBtn variant="translucent" color="accent">accent</RBtn>
        <RBtn variant="translucent" color="success">success</RBtn>
        <RBtn variant="translucent" color="warning">warning</RBtn>
        <RBtn variant="translucent" color="danger">danger</RBtn>
        <RBtn variant="translucent" color="info">info</RBtn>
      </div>
    `,
  }),
};

// ── Icons ───────────────────────────────────────────────────────────

export const WithIcons: Story = {
  name: "Prepend / append icons",
  render: () => ({
    components: { RBtn },
    template: `
      <div style="display:flex;flex-wrap:wrap;gap:10px">
        <RBtn color="primary" prepend-icon="mdi-login">Sign in</RBtn>
        <RBtn color="success" prepend-icon="mdi-content-save">Save</RBtn>
        <RBtn variant="outlined" append-icon="mdi-open-in-new">Open docs</RBtn>
        <RBtn variant="translucent" color="primary" prepend-icon="mdi-filter" append-icon="mdi-menu-down">Filter</RBtn>
      </div>
    `,
  }),
};

export const IconOnly: Story = {
  name: "Icon-only buttons",
  render: () => ({
    components: { RBtn },
    template: `
      <div style="display:flex;align-items:center;gap:10px">
        <RBtn icon="mdi-pencil" variant="text" aria-label="Edit" />
        <RBtn icon="mdi-delete" variant="text" color="danger" aria-label="Delete" />
        <RBtn icon="mdi-heart" variant="translucent" color="primary" aria-label="Favorite" />
        <RBtn icon="mdi-refresh" variant="outlined" aria-label="Refresh" />
        <RBtn icon="mdi-plus" color="primary" aria-label="Add" />
      </div>
    `,
  }),
};

export const IconSizeLadder: Story = {
  name: "Icon-only · size ladder",
  render: () => ({
    components: { RBtn },
    template: `
      <div style="display:flex;align-items:center;gap:10px">
        <RBtn icon="mdi-star" size="x-small" color="primary" aria-label="x-small" />
        <RBtn icon="mdi-star" size="small" color="primary" aria-label="small" />
        <RBtn icon="mdi-star" size="default" color="primary" aria-label="default" />
        <RBtn icon="mdi-star" size="large" color="primary" aria-label="large" />
        <RBtn icon="mdi-star" size="x-large" color="primary" aria-label="x-large" />
      </div>
    `,
  }),
};

// Icon-mode button with custom default-slot content. When `icon` is
// set as a flag (boolean / empty / `true`) and a default slot is
// provided, the slot replaces the icon glyph. Used for composite icon
// content like GameCard's platform badge, where the "icon" is an
// RPlatformIcon SVG rather than an MDI codepoint.
export const IconSlotCustom: Story = {
  name: "Icon-mode · custom slot content",
  render: () => ({
    components: { RBtn },
    template: `
      <div style="display:flex;align-items:center;gap:10px">
        <RBtn icon variant="translucent" color="primary" aria-label="Image button" style="width:auto;min-width:0;padding:3px">
          <img src="https://placehold.co/22x22/A66/fff?text=P" alt="Platform" style="display:block;width:22px;height:22px;border-radius:3px" />
        </RBtn>
        <RBtn icon variant="text" aria-label="Emoji button" style="width:auto;min-width:0;padding:3px">
          <span style="font-size:18px;line-height:1">🎮</span>
        </RBtn>
        <RBtn icon variant="outlined" aria-label="Mixed content" style="width:auto;min-width:0;padding:3px 8px">
          <span style="display:inline-flex;align-items:center;gap:4px;font-size:12px">⭐ <span>9</span></span>
        </RBtn>
      </div>
    `,
  }),
  parameters: {
    docs: {
      description: {
        story:
          "Pass `icon` as a flag and put custom content in the default slot. RBtn renders the content inside `.r-btn__icon-slot` with `line-height: 0` so descender gaps from text/icons don't shift the centering.",
      },
    },
  },
};

// ── Rounded ─────────────────────────────────────────────────────────

export const Rounded: Story = {
  name: "Rounded ladder",
  render: () => ({
    components: { RBtn },
    template: `
      <div style="display:flex;flex-wrap:wrap;gap:10px;align-items:center">
        <RBtn :rounded="0" color="primary">0</RBtn>
        <RBtn rounded="sm" color="primary">sm</RBtn>
        <RBtn rounded="md" color="primary">md (default)</RBtn>
        <RBtn rounded="lg" color="primary">lg</RBtn>
        <RBtn rounded="xl" color="primary">xl</RBtn>
        <RBtn rounded="full" color="primary">full / pill</RBtn>
      </div>
    `,
  }),
};

// ── Loading ─────────────────────────────────────────────────────────

export const LoadingState: Story = {
  name: "Loading (interactive)",
  render: () => ({
    components: { RBtn },
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
        <RBtn color="primary" :loading="loading" prepend-icon="mdi-content-save" @click="run">
          Save changes
        </RBtn>
        <RBtn variant="outlined" :loading="loading" @click="run">Submit</RBtn>
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
    components: { RBtn },
    setup: () => ({ args }),
    template: `<div style="width:360px"><RBtn v-bind="args">Submit</RBtn></div>`,
  }),
};

export const Disabled: Story = {
  render: () => ({
    components: { RBtn },
    template: `
      <div style="display:flex;flex-wrap:wrap;gap:10px">
        <RBtn disabled>disabled flat</RBtn>
        <RBtn variant="outlined" disabled>disabled outlined</RBtn>
        <RBtn variant="translucent" color="primary" disabled>disabled translucent</RBtn>
        <RBtn variant="text" color="danger" disabled>disabled text</RBtn>
        <RBtn icon="mdi-delete" variant="text" disabled aria-label="disabled icon" />
      </div>
    `,
  }),
};

// ── Border modifier ─────────────────────────────────────────────────

export const BorderModifier: Story = {
  name: "Border modifier (chip-style activator)",
  render: () => ({
    components: { RBtn },
    template: `
      <div style="display:flex;flex-wrap:wrap;gap:10px;align-items:center">
        <RBtn variant="translucent" color="primary" border>translucent + border</RBtn>
        <RBtn variant="text" color="primary" border>text + border</RBtn>
        <RBtn variant="translucent" color="accent" border rounded="full">activator pill</RBtn>
      </div>
    `,
  }),
};

// ── Polymorphic root ────────────────────────────────────────────────

export const AsLink: Story = {
  name: "Polymorphic (href / to)",
  render: () => ({
    components: { RBtn },
    template: `
      <div style="display:flex;flex-direction:column;gap:12px;align-items:flex-start">
        <RBtn href="https://romm.app" target="_blank" append-icon="mdi-open-in-new" color="primary">
          External link (&lt;a&gt;)
        </RBtn>
        <span style="font:12px/1.4 sans-serif;color:var(--r-color-fg-muted)">
          With <code>to</code>, RBtn renders <code>&lt;router-link&gt;</code> — invisible in this story without a router, but the prop is accepted.
        </span>
      </div>
    `,
  }),
};

// ── Real-world stacks ───────────────────────────────────────────────

export const Toolbar: Story = {
  name: "Toolbar row",
  render: () => ({
    components: { RBtn },
    template: `
      <div style="display:inline-flex;align-items:center;gap:6px;padding:6px 8px;background:var(--r-color-surface);border-radius:10px">
        <RBtn icon="mdi-format-bold" variant="text" size="small" aria-label="Bold" />
        <RBtn icon="mdi-format-italic" variant="text" size="small" aria-label="Italic" />
        <RBtn icon="mdi-format-underline" variant="text" size="small" aria-label="Underline" />
        <span style="width:1px;height:18px;background:var(--r-color-border);margin:0 4px"></span>
        <RBtn icon="mdi-format-list-bulleted" variant="text" size="small" aria-label="List" />
        <RBtn icon="mdi-format-quote-close" variant="text" size="small" aria-label="Quote" />
        <RBtn icon="mdi-link-variant" variant="text" size="small" aria-label="Link" />
      </div>
    `,
  }),
};

export const FormActions: Story = {
  name: "Form actions row",
  render: () => ({
    components: { RBtn },
    template: `
      <div style="display:flex;gap:10px;justify-content:flex-end;padding:14px;background:var(--r-color-bg-elevated);border-radius:10px;width:420px">
        <RBtn variant="text">Cancel</RBtn>
        <RBtn variant="outlined">Save draft</RBtn>
        <RBtn color="primary" prepend-icon="mdi-send">Publish</RBtn>
      </div>
    `,
  }),
};

// Surface modifier — pairs an outlined icon-only RBtn with an
// `RSliderBtnGroup` segmented cluster so both share the same tinted
// chrome. Used in `GalleryToolbar` for filter / kebab buttons.
export const SurfaceWithSlider: Story = {
  name: "Surface modifier (icon button next to slider)",
  render: () => ({
    components: { RBtn },
    template: `
      <div style="display:flex;gap:8px;align-items:center;padding:16px;background:var(--r-color-bg);width:max-content">
        <RBtn variant="outlined" surface icon="mdi-filter-variant" rounded="circle" aria-label="Filters" />
        <div style="display:inline-flex;align-items:center;gap:2px;padding:2px;background:var(--r-color-bg-elevated);border:1px solid var(--r-color-border);border-radius:999px;font-size:11px;color:var(--r-color-fg-muted)">
          <span style="padding:4px 10px">Mock slider wrapper for comparison</span>
        </div>
        <RBtn variant="outlined" surface icon="mdi-dots-vertical" rounded="circle" aria-label="More" />
      </div>
      <p style="margin:8px 0 0 16px;font:12px monospace;color:var(--r-color-fg-muted);max-width:480px">
        \`surface\` paints --r-color-bg-elevated so the disc-shaped icon
        button reads as a sibling of the segmented slider next to it.
      </p>
    `,
  }),
};
