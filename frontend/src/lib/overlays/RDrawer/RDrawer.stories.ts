import type { Meta, StoryObj } from "@storybook/vue3-vite";
import { ref } from "vue";
import RTextField from "@/lib/forms/RTextField/RTextField.vue";
import RButton from "@/lib/primitives/RButton/RButton.vue";
import { a11yTodoRules } from "@/utils/storyA11y";
import RDrawer from "./RDrawer.vue";

const meta: Meta<typeof RDrawer> = {
  title: "Overlays/RDrawer",
  component: RDrawer,
  argTypes: {
    side: { control: "inline-radio", options: ["left", "right"] },
    width: { control: "text" },
    icon: { control: "text" },
  },
};

export default meta;
type Story = StoryObj<typeof RDrawer>;

// ── Right-side default ────────────────────────────────────────

export const Default: Story = {
  args: { side: "right", width: 380, icon: "mdi-filter-variant" },
  render: (args) => ({
    components: { RDrawer, RButton },
    setup: () => ({ args, open: ref(false) }),
    template: `
      <div style="height:480px;padding:24px;display:flex;align-items:flex-start">
        <RButton variant="flat" color="primary" @click="open = true">Open drawer</RButton>
        <RDrawer v-bind="args" v-model="open">
          <template #header>Filters</template>
          <p style="margin:0 0 12px 0;color:var(--r-color-fg-muted);font-size:13px">
            Drawer body. Pick a side, give it a width, drop your controls in
            the default slot.
          </p>
          <template #footer>
            <RButton variant="text" color="danger" @click="open = false">Cancel</RButton>
            <div style="flex:1"></div>
            <RButton variant="flat" color="primary" @click="open = false">Apply</RButton>
          </template>
        </RDrawer>
      </div>
    `,
  }),
};

// ── Left-side variant ─────────────────────────────────────────

export const LeftSide: Story = {
  name: "Left side",
  args: { side: "left", width: 320, icon: "mdi-menu" },
  render: (args) => ({
    components: { RDrawer, RButton },
    setup: () => ({ args, open: ref(false) }),
    template: `
      <div style="height:480px;padding:24px;display:flex;align-items:flex-start;justify-content:flex-end">
        <RButton variant="flat" @click="open = true">Open left drawer</RButton>
        <RDrawer v-bind="args" v-model="open">
          <template #header>Navigation</template>
          <ul style="margin:0;padding:0;list-style:none;display:flex;flex-direction:column;gap:8px">
            <li>Home</li>
            <li>Library</li>
            <li>Stats</li>
            <li>Settings</li>
          </ul>
        </RDrawer>
      </div>
    `,
  }),
};

// ── Tall content scrolls inside the body ──────────────────────

export const TallContent: Story = {
  name: "Tall content (scrolling body)",
  // The scrolling body can't take keyboard focus.
  args: { side: "right", width: 380, icon: "mdi-format-list-bulleted" },
  // Opens on mount, so the docs page renders it in its own iframe to keep
  // the fixed drawer from covering the page.
  parameters: {
    ...a11yTodoRules("color-contrast", "scrollable-region-focusable"),
    docs: { story: { inline: false, height: "560px" } },
  },
  render: (args) => ({
    components: { RDrawer, RButton, RTextField },
    setup: () => ({
      args,
      open: ref(true),
      rows: Array.from({ length: 30 }, (_, i) => `Row ${i + 1}`),
    }),
    template: `
      <div style="height:480px;padding:24px">
        <RButton variant="flat" color="primary" @click="open = true">Open</RButton>
        <RDrawer v-bind="args" v-model="open">
          <template #header>Long list</template>
          <ul style="margin:0;padding:0;list-style:none;display:flex;flex-direction:column;gap:6px">
            <li v-for="r in rows" :key="r" style="padding:8px 10px;border-radius:6px;background:var(--r-color-surface)">
              {{ r }}
            </li>
          </ul>
          <template #footer>
            <div style="flex:1"></div>
            <RButton variant="flat" color="primary" @click="open = false">Done</RButton>
          </template>
        </RDrawer>
      </div>
    `,
  }),
};

// ── Persistent (no close on scrim / Escape) ──────────────────

export const Persistent: Story = {
  args: { side: "right", width: 360, persistent: true, icon: "mdi-lock" },
  render: (args) => ({
    components: { RDrawer, RButton },
    setup: () => ({ args, open: ref(false) }),
    template: `
      <div style="height:480px;padding:24px">
        <RButton variant="flat" color="primary" @click="open = true">Open persistent</RButton>
        <RDrawer v-bind="args" v-model="open">
          <template #header>Confirm before leaving</template>
          <p style="margin:0;color:var(--r-color-fg-muted)">
            Scrim clicks and Escape are blocked. Only the close button or
            explicit Cancel / Continue exits the drawer.
          </p>
          <template #footer>
            <RButton variant="text" color="danger" @click="open = false">Cancel</RButton>
            <div style="flex:1"></div>
            <RButton variant="flat" color="primary" @click="open = false">Continue</RButton>
          </template>
        </RDrawer>
      </div>
    `,
  }),
};
