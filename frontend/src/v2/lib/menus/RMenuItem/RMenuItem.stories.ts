import type { Meta, StoryObj } from "@storybook/vue3-vite";
import { expect, fn, within } from "storybook/test";
import RMenuItem from "./RMenuItem.vue";

// Glass-panel mock so the items render against the same surface they'd
// have inside an RMenu (without needing to mount the floating menu).
const PANEL_STYLE = [
  "width: 240px",
  "padding: 6px",
  "background: var(--r-color-panel)",
  "border: 1px solid var(--r-color-panel-border)",
  "border-radius: 10px",
  "backdrop-filter: blur(28px)",
].join(";");

const meta: Meta<typeof RMenuItem> = {
  title: "Menus/RMenuItem",
  component: RMenuItem,
  argTypes: {
    label: { control: "text" },
    icon: { control: "text" },
    variant: {
      control: "select",
      options: ["default", "active", "danger"],
    },
    disabled: { control: "boolean" },
    to: { control: "text" },
    href: { control: "text" },
    closeOnClick: { control: "boolean" },
  },
  render: (args) => ({
    components: { RMenuItem },
    setup: () => ({ args, panelStyle: PANEL_STYLE }),
    template: `
      <div style="padding:40px">
        <div :style="panelStyle">
          <RMenuItem v-bind="args" />
        </div>
      </div>
    `,
  }),
};

export default meta;

type Story = StoryObj<typeof RMenuItem>;

export const Default: Story = {
  args: { label: "Play", icon: "mdi-play" },
};

export const Active: Story = {
  args: { label: "Favorited", icon: "mdi-heart", variant: "active" },
};

export const Danger: Story = {
  args: { label: "Delete…", icon: "mdi-trash-can-outline", variant: "danger" },
};

export const Disabled: Story = {
  args: { label: "Disabled", icon: "mdi-cog-outline", disabled: true },
};

export const Variants: Story = {
  render: () => ({
    components: { RMenuItem },
    setup: () => ({ panelStyle: PANEL_STYLE }),
    template: `
      <div style="padding:40px">
        <div :style="panelStyle">
          <RMenuItem label="Default" icon="mdi-play" />
          <RMenuItem label="With subtitle" icon="mdi-download-outline" />
          <RMenuItem label="Active (favorited)" icon="mdi-heart" variant="active" />
          <RMenuItem label="Danger / destructive" icon="mdi-trash-can-outline" variant="danger" />
          <RMenuItem label="Disabled" icon="mdi-cog-outline" disabled />
        </div>
      </div>
    `,
  }),
};

export const WithNavigation: Story = {
  render: () => ({
    components: { RMenuItem },
    setup: () => ({ panelStyle: PANEL_STYLE }),
    template: `
      <div style="padding:40px">
        <div :style="panelStyle">
          <RMenuItem to="/platforms" icon="mdi-gamepad-variant-outline" label="Platforms" />
          <RMenuItem href="https://romm.app" icon="mdi-open-in-new" label="External link" />
        </div>
      </div>
    `,
  }),
};

// A new-tab / new-window gesture (Ctrl/⌘/Shift/Alt-click) on a link item
// must NOT fire the `click` emit — consumers wire that to "close the menu",
// and closing would unmount the <a> before the browser opens the new tab.
// A plain click still activates the item normally.
export const NewTabGesture: Story = {
  name: "New-tab gesture (Ctrl/⌘-click)",
  args: {
    href: "#platforms",
    icon: "mdi-open-in-new",
    label: "Open in new tab",
    onClick: fn(),
  },
  render: (args) => ({
    components: { RMenuItem },
    setup: () => ({ args, panelStyle: PANEL_STYLE }),
    template: `
      <div style="padding:40px">
        <div :style="panelStyle">
          <RMenuItem v-bind="args" @click="args.onClick" />
        </div>
      </div>
    `,
  }),
  play: async ({ canvasElement, args, step }) => {
    const canvas = within(canvasElement);
    const link = canvas.getByText("Open in new tab").closest("a");
    if (!link) throw new Error("expected the item to render as an <a>");

    await step("plain click activates the item", async () => {
      link.dispatchEvent(
        new MouseEvent("click", { bubbles: true, cancelable: true }),
      );
      await expect(args.onClick).toHaveBeenCalledTimes(1);
    });

    await step(
      "Ctrl-click is suppressed (browser opens a new tab)",
      async () => {
        link.dispatchEvent(
          new MouseEvent("click", {
            bubbles: true,
            cancelable: true,
            ctrlKey: true,
          }),
        );
        // Still 1 — the emit was suppressed so a consumer's close handler
        // never runs and the <a> survives for the browser's default action.
        await expect(args.onClick).toHaveBeenCalledTimes(1);
      },
    );
  },
};
