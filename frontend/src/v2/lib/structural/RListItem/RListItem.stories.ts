import type { Meta, StoryObj } from "@storybook/vue3-vite";
import { ref } from "vue";
import RList from "../RList/RList.vue";
import RListItem from "./RListItem.vue";

const meta: Meta<typeof RListItem> = {
  title: "Structural/RListItem",
  component: RListItem,
  argTypes: {
    title: { control: "text" },
    subtitle: { control: "text" },
    prependIcon: { control: "text" },
    appendIcon: { control: "text" },
    prependAvatar: { control: "text" },
    active: { control: "boolean" },
    disabled: { control: "boolean" },
    rounded: { control: "text" },
  },
  render: (args) => ({
    components: { RList, RListItem },
    setup: () => ({ args }),
    template: `
      <div style="width:300px;border:1px solid var(--r-color-border);border-radius:var(--r-radius-md);background:var(--r-color-bg-elevated)">
        <RList>
          <RListItem v-bind="args" />
        </RList>
      </div>
    `,
  }),
};

export default meta;

type Story = StoryObj<typeof RListItem>;

// Shared wrap snippet to keep the demos consistent.
const SHELL = `style="width:300px;border:1px solid var(--r-color-border);border-radius:var(--r-radius-md);background:var(--r-color-bg-elevated)"`;

// ── Defaults ────────────────────────────────────────────────────────

export const Default: Story = {
  args: { title: "Plain item" },
};

export const WithIcon: Story = {
  args: { title: "With prepend icon", prependIcon: "mdi-play" },
};

export const TwoLine: Story = {
  args: {
    title: "Two-line row",
    subtitle: "Subtitle lives here",
    prependIcon: "mdi-star",
  },
};

export const Active: Story = {
  args: { title: "Active state", prependIcon: "mdi-cog", active: true },
};

export const Disabled: Story = {
  args: {
    title: "Disabled item",
    subtitle: "Pointer events suppressed",
    prependIcon: "mdi-lock",
    disabled: true,
  },
};

// ── Prepend zone ────────────────────────────────────────────────────

export const PrependVariants: Story = {
  name: "Prepend · icon / avatar / slot",
  render: () => ({
    components: { RList, RListItem },
    template: `
      <div ${SHELL}>
        <RList>
          <RListItem prepend-icon="mdi-account" title="Prepend icon" />
          <RListItem prepend-avatar="/assets/isotipo.svg" title="Prepend avatar" />
          <RListItem title="Custom prepend slot">
            <template #prepend>
              <span style="display:inline-flex;align-items:center;justify-content:center;width:28px;height:28px;border-radius:6px;background:var(--r-color-success);color:white;font:600 11px/1 sans-serif">7</span>
            </template>
          </RListItem>
        </RList>
      </div>
    `,
  }),
};

export const AppendIcon: Story = {
  name: "Append icon (chevron right)",
  render: () => ({
    components: { RList, RListItem },
    template: `
      <div ${SHELL}>
        <RList>
          <RListItem prepend-icon="mdi-account" title="Profile" append-icon="mdi-chevron-right" />
          <RListItem prepend-icon="mdi-bell" title="Notifications" append-icon="mdi-chevron-right" />
          <RListItem prepend-icon="mdi-cog" title="Settings" append-icon="mdi-chevron-right" />
        </RList>
      </div>
    `,
  }),
};

// ── Interactive ────────────────────────────────────────────────────

export const Interactive: Story = {
  name: "Click handler (interactive)",
  render: () => ({
    components: { RList, RListItem },
    setup() {
      const log = ref<string[]>([]);
      function fire(name: string) {
        log.value = [...log.value, `Clicked ${name}`].slice(-4);
      }
      return { log, fire };
    },
    template: `
      <div style="display:flex;gap:20px;align-items:flex-start">
        <div ${SHELL}>
          <RList>
            <RListItem prepend-icon="mdi-pencil" title="Edit" @click="fire('Edit')" />
            <RListItem prepend-icon="mdi-content-copy" title="Duplicate" @click="fire('Duplicate')" />
            <RListItem prepend-icon="mdi-share-variant" title="Share" @click="fire('Share')" />
            <RListItem prepend-icon="mdi-delete" title="Delete" @click="fire('Delete')" />
          </RList>
        </div>
        <div style="font:12px/1.5 monospace;color:var(--r-color-fg-muted);min-width:160px">
          <div style="margin-bottom:6px;color:var(--r-color-fg-faint)">log:</div>
          <div v-for="(l, i) in log" :key="i">{{ l }}</div>
          <div v-if="!log.length">(no clicks yet)</div>
        </div>
      </div>
    `,
  }),
};

export const NonInteractive: Story = {
  name: "Display-only (no hover)",
  render: () => ({
    components: { RList, RListItem },
    template: `
      <div ${SHELL}>
        <RList>
          <RListItem prepend-icon="mdi-information" title="Read-only row" subtitle="Hover doesn't tint" />
          <RListItem prepend-icon="mdi-format-list-bulleted" title="No click handler" subtitle="No to / href / @click" />
        </RList>
      </div>
    `,
  }),
};

// ── Polymorphic ─────────────────────────────────────────────────────

export const AsLink: Story = {
  name: "Polymorphic (href / to)",
  render: () => ({
    components: { RList, RListItem },
    template: `
      <div ${SHELL}>
        <RList>
          <RListItem
            href="https://romm.app"
            target="_blank"
            prepend-icon="mdi-link-variant"
            append-icon="mdi-open-in-new"
            title="External link (&lt;a&gt;)"
            subtitle="opens in new tab"
          />
          <RListItem
            href="#"
            prepend-icon="mdi-account"
            title="Anchor disabled"
            subtitle="href stripped — keyboard inert"
            disabled
          />
        </RList>
      </div>
    `,
  }),
};

// ── Gallery ─────────────────────────────────────────────────────────

export const Gallery: Story = {
  render: () => ({
    components: { RList, RListItem },
    template: `
      <div ${SHELL}>
        <RList>
          <RListItem title="Plain item" />
          <RListItem prepend-icon="mdi-play" title="With prepend icon" />
          <RListItem prepend-icon="mdi-star" title="Two-line row" subtitle="Subtitle lives here" />
          <RListItem prepend-icon="mdi-cog" title="Active state" active />
          <RListItem prepend-icon="mdi-lock" title="Disabled" disabled />
          <RListItem
            prepend-avatar="/assets/isotipo.svg"
            title="With avatar"
            append-icon="mdi-chevron-right"
          />
        </RList>
      </div>
    `,
  }),
};
