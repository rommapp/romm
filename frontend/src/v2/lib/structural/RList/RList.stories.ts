import type { Meta, StoryObj } from "@storybook/vue3-vite";
import RListItem from "../RListItem/RListItem.vue";
import RList from "./RList.vue";

const meta: Meta<typeof RList> = {
  title: "Structural/RList",
  component: RList,
  argTypes: {
    density: {
      control: "select",
      options: ["default", "comfortable", "compact"],
    },
    rounded: { control: "text" },
    color: { control: "text" },
    bgColor: { control: "text" },
  },
};

export default meta;

type Story = StoryObj<typeof RList>;

// Reusable wrap so stories share the framing chrome.
const SHELL = `style="width:280px;border:1px solid var(--r-color-border);border-radius:var(--r-radius-md);background:var(--r-color-bg-elevated)"`;

// ── Defaults ────────────────────────────────────────────────────────

export const Navigation: Story = {
  render: (args) => ({
    components: { RList, RListItem },
    setup: () => ({ args }),
    template: `
      <div ${SHELL}>
        <RList v-bind="args">
          <RListItem prepend-icon="mdi-home" title="Home" active />
          <RListItem prepend-icon="mdi-controller" title="Platforms" />
          <RListItem prepend-icon="mdi-bookmark-box-multiple" title="Collections" />
          <RListItem prepend-icon="mdi-magnify" title="Search" />
          <RListItem prepend-icon="mdi-cog" title="Settings" />
        </RList>
      </div>
    `,
  }),
};

// ── Density ─────────────────────────────────────────────────────────

export const Density: Story = {
  name: "Density compression",
  render: () => ({
    components: { RList, RListItem },
    template: `
      <div style="display:flex;gap:18px">
        <div ${SHELL}>
          <RList density="default">
            <RListItem prepend-icon="mdi-home" title="Default" />
            <RListItem prepend-icon="mdi-controller" title="Density" />
            <RListItem prepend-icon="mdi-magnify" title="Spacious" />
          </RList>
        </div>
        <div ${SHELL}>
          <RList density="comfortable">
            <RListItem prepend-icon="mdi-home" title="Comfortable" />
            <RListItem prepend-icon="mdi-controller" title="Density" />
            <RListItem prepend-icon="mdi-magnify" title="Mid-tight" />
          </RList>
        </div>
        <div ${SHELL}>
          <RList density="compact">
            <RListItem prepend-icon="mdi-home" title="Compact" />
            <RListItem prepend-icon="mdi-controller" title="Density" />
            <RListItem prepend-icon="mdi-magnify" title="Tight rows" />
          </RList>
        </div>
      </div>
    `,
  }),
};

// ── Active tone ─────────────────────────────────────────────────────

export const ActiveColor: Story = {
  name: "Active tone (color prop)",
  render: () => ({
    components: { RList, RListItem },
    template: `
      <div style="display:flex;gap:18px">
        <div ${SHELL}>
          <RList color="primary">
            <RListItem prepend-icon="mdi-home" title="primary" active />
            <RListItem prepend-icon="mdi-controller" title="active tone" />
          </RList>
        </div>
        <div ${SHELL}>
          <RList color="success">
            <RListItem prepend-icon="mdi-home" title="success" active />
            <RListItem prepend-icon="mdi-controller" title="active tone" />
          </RList>
        </div>
        <div ${SHELL}>
          <RList color="danger">
            <RListItem prepend-icon="mdi-home" title="danger" active />
            <RListItem prepend-icon="mdi-controller" title="active tone" />
          </RList>
        </div>
      </div>
    `,
  }),
};

// ── Background paint ────────────────────────────────────────────────

export const SelfPainted: Story = {
  name: "Self-painted list (bgColor)",
  render: () => ({
    components: { RList, RListItem },
    template: `
      <RList bg-color="var(--r-color-bg-elevated)" style="width:280px;border:1px solid var(--r-color-border)">
        <RListItem prepend-icon="mdi-account" title="With bgColor set" />
        <RListItem prepend-icon="mdi-bell" title="No outer wrapper needed" />
        <RListItem prepend-icon="mdi-cog" title="List paints itself" />
      </RList>
    `,
  }),
};

// ── Real-world ──────────────────────────────────────────────────────

export const SidebarNav: Story = {
  name: "Sidebar nav (Settings sidebar)",
  render: () => ({
    components: { RList, RListItem },
    template: `
      <div ${SHELL}>
        <RList>
          <RListItem prepend-icon="mdi-account-circle" title="User profile" />
          <RListItem prepend-icon="mdi-palette" title="User interface" active />
          <RListItem prepend-icon="mdi-key-variant" title="Client API tokens" />
          <RListItem prepend-icon="mdi-shield-account" title="Administration" />
          <RListItem prepend-icon="mdi-folder-multiple-outline" title="Library management" />
          <RListItem prepend-icon="mdi-database" title="Metadata sources" />
        </RList>
      </div>
    `,
  }),
};

export const UserMenu: Story = {
  name: "User menu (with subtitle)",
  render: () => ({
    components: { RList, RListItem },
    template: `
      <div ${SHELL}>
        <RList density="comfortable">
          <RListItem
            prepend-avatar="/assets/isotipo.svg"
            title="RomM Admin"
            subtitle="admin · last seen 3 min ago"
          />
          <RListItem prepend-icon="mdi-account" title="Your profile" />
          <RListItem prepend-icon="mdi-cog" title="Settings" />
          <RListItem prepend-icon="mdi-theme-light-dark" title="Toggle theme" append-icon="mdi-chevron-right" />
          <RListItem prepend-icon="mdi-logout" title="Sign out" />
        </RList>
      </div>
    `,
  }),
};
