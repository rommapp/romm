import type { Meta, StoryObj } from "@storybook/vue3-vite";
import RBtn from "@/v2/lib/primitives/RBtn/RBtn.vue";
import RIcon from "@/v2/lib/primitives/RIcon/RIcon.vue";
import RToolbar from "./RToolbar.vue";

const meta: Meta<typeof RToolbar> = {
  title: "Structural/RToolbar",
  component: RToolbar,
  argTypes: {
    title: { control: "text" },
    color: { control: "text" },
    density: {
      control: "select",
      options: ["default", "comfortable", "compact"],
    },
    flat: { control: "boolean" },
    height: { control: "text" },
    rounded: { control: "text" },
  },
};

export default meta;

type Story = StoryObj<typeof RToolbar>;

// ── Defaults ────────────────────────────────────────────────────────

export const Default: Story = {
  args: { title: "Platforms" },
  render: (args) => ({
    components: { RToolbar },
    setup: () => ({ args }),
    template: `
      <div style="width:720px;border-radius:8px;overflow:hidden;border:1px solid var(--r-color-border)">
        <RToolbar v-bind="args" />
      </div>
    `,
  }),
};

export const WithActions: Story = {
  name: "Title + append actions",
  args: { title: "Platforms" },
  render: (args) => ({
    components: { RToolbar, RBtn },
    setup: () => ({ args }),
    template: `
      <div style="width:720px;border-radius:8px;overflow:hidden;border:1px solid var(--r-color-border)">
        <RToolbar v-bind="args">
          <template #append>
            <RBtn variant="text" prepend-icon="mdi-filter">Filters</RBtn>
            <RBtn variant="text" prepend-icon="mdi-sort">Sort</RBtn>
          </template>
        </RToolbar>
      </div>
    `,
  }),
};

export const WithPrepend: Story = {
  name: "Prepend (back button)",
  args: { title: "Super Mario Bros." },
  render: (args) => ({
    components: { RToolbar, RBtn },
    setup: () => ({ args }),
    template: `
      <div style="width:720px;border-radius:8px;overflow:hidden;border:1px solid var(--r-color-border)">
        <RToolbar v-bind="args">
          <template #prepend>
            <RBtn icon="mdi-arrow-left" variant="text" aria-label="Back" />
          </template>
          <template #append>
            <RBtn icon="mdi-pencil" variant="text" aria-label="Edit" />
            <RBtn icon="mdi-dots-vertical" variant="text" aria-label="More" />
          </template>
        </RToolbar>
      </div>
    `,
  }),
};

// ── Density ─────────────────────────────────────────────────────────

export const DensityLadder: Story = {
  name: "Density ladder",
  render: () => ({
    components: { RToolbar, RBtn },
    template: `
      <div style="display:flex;flex-direction:column;gap:14px;width:720px">
        <div style="border-radius:8px;overflow:hidden;border:1px solid var(--r-color-border)">
          <RToolbar title="Default · 64px">
            <template #append>
              <RBtn variant="text" size="small">Action</RBtn>
            </template>
          </RToolbar>
        </div>
        <div style="border-radius:8px;overflow:hidden;border:1px solid var(--r-color-border)">
          <RToolbar density="comfortable" title="Comfortable · 56px">
            <template #append>
              <RBtn variant="text" size="small">Action</RBtn>
            </template>
          </RToolbar>
        </div>
        <div style="border-radius:8px;overflow:hidden;border:1px solid var(--r-color-border)">
          <RToolbar density="compact" title="Compact · 48px">
            <template #append>
              <RBtn variant="text" size="small">Action</RBtn>
            </template>
          </RToolbar>
        </div>
      </div>
    `,
  }),
};

// ── Variants ────────────────────────────────────────────────────────

export const Flat: Story = {
  name: "Flat (no bottom border)",
  args: { title: "Settings", flat: true },
  render: (args) => ({
    components: { RToolbar, RBtn },
    setup: () => ({ args }),
    template: `
      <div style="width:720px">
        <RToolbar v-bind="args">
          <template #append>
            <RBtn variant="text">Reset</RBtn>
            <RBtn color="primary">Save</RBtn>
          </template>
        </RToolbar>
        <div style="padding:24px;color:var(--r-color-fg-muted);font:12px/1.4 sans-serif">
          Toolbar sits flush with the body — no hairline divider.
        </div>
      </div>
    `,
  }),
};

export const Colored: Story = {
  name: "Coloured toolbars",
  render: () => ({
    components: { RToolbar, RBtn },
    template: `
      <div style="display:flex;flex-direction:column;gap:14px;width:720px">
        <RToolbar color="primary" title="Primary">
          <template #append>
            <RBtn variant="text" prepend-icon="mdi-bell" />
            <RBtn variant="text" prepend-icon="mdi-account-circle" />
          </template>
        </RToolbar>
        <RToolbar color="success" title="Success — scan complete">
          <template #prepend>
            <RBtn icon="mdi-check-circle" variant="text" aria-label="ok" />
          </template>
        </RToolbar>
        <RToolbar color="danger" title="Connection lost">
          <template #append>
            <RBtn variant="text">Retry</RBtn>
          </template>
        </RToolbar>
      </div>
    `,
  }),
};

// ── Rounded + height ────────────────────────────────────────────────

export const RoundedAndHeight: Story = {
  name: "Rounded + custom height",
  render: () => ({
    components: { RToolbar, RBtn },
    template: `
      <div style="display:flex;flex-direction:column;gap:14px;width:720px">
        <RToolbar rounded="lg" title="rounded='lg'">
          <template #append>
            <RBtn variant="text" prepend-icon="mdi-cog">Settings</RBtn>
          </template>
        </RToolbar>
        <RToolbar :height="80" title="height=80 (taller)">
          <template #append>
            <RBtn color="primary" prepend-icon="mdi-plus">Add</RBtn>
          </template>
        </RToolbar>
      </div>
    `,
  }),
};

// ── Real-world ──────────────────────────────────────────────────────

export const GalleryHeader: Story = {
  name: "Gallery header (real-world)",
  render: () => ({
    components: { RToolbar, RBtn, RIcon },
    template: `
      <div style="width:720px;border-radius:12px;overflow:hidden;border:1px solid var(--r-color-border);background:var(--r-color-bg-elevated)">
        <RToolbar title="Nintendo 64" flat>
          <template #prepend>
            <RBtn icon="mdi-arrow-left" variant="text" aria-label="Back" />
          </template>
          <template #append>
            <RBtn variant="text" prepend-icon="mdi-magnify" />
            <RBtn variant="text" prepend-icon="mdi-filter">Filters</RBtn>
            <RBtn variant="text" prepend-icon="mdi-sort-variant">Sort</RBtn>
            <RBtn icon="mdi-dots-vertical" variant="text" aria-label="More" />
          </template>
        </RToolbar>
        <div style="padding:20px;color:var(--r-color-fg-muted);font:13px/1.5 sans-serif">
          128 ROMs · 4 missing · last scan 3 hours ago
        </div>
      </div>
    `,
  }),
};

export const DialogTitleRow: Story = {
  name: "Dialog title row",
  render: () => ({
    components: { RToolbar, RBtn },
    template: `
      <div style="width:480px;border-radius:12px;overflow:hidden;border:1px solid var(--r-color-border);background:var(--r-color-bg-elevated);box-shadow:0 12px 30px color-mix(in srgb, black 30%, transparent)">
        <RToolbar density="compact" title="Edit ROM" flat>
          <template #append>
            <RBtn icon="mdi-close" variant="text" aria-label="Close" />
          </template>
        </RToolbar>
        <div style="padding:18px 16px;color:var(--r-color-fg-muted);font:13px/1.5 sans-serif">
          Dialog body — toolbar acts as the title row.
        </div>
      </div>
    `,
  }),
};
