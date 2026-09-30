import type { Meta, StoryObj } from "@storybook/vue3-vite";
import { expect, userEvent, within } from "storybook/test";
import type { InstallSessionState } from "@/__generated__";
import { makeRom } from "@/utils/rom.fixtures";
import InstallButton from "@/v2/components/GameDetails/InstallButton.vue";
import { useInstallSession } from "@/v2/composables/useInstallSession";
import { makeInstallSession } from "@/v2/utils/install.fixtures";

const rom = makeRom({ id: 1, name: "Example Game", platform_slug: "win" });

// Drives the real composable: seeding `session` is enough, since it makes no
// requests until a method is called.
function renderWith(state: InstallSessionState) {
  return () => ({
    components: { InstallButton },
    setup() {
      const install = useInstallSession(() => rom);
      install.session.value = makeInstallSession(state);
      return { install, rom };
    },
    template: `<InstallButton :install="install" :rom="rom" />`,
  });
}

const meta: Meta<typeof InstallButton> = {
  title: "GameDetails/InstallButton",
  component: InstallButton,
};

export default meta;
type Story = StoryObj<typeof InstallButton>;

export const Installing: Story = {
  render: renderWith("installing"),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(
      canvas.getByRole("button", { name: /installing/i }),
    ).toBeVisible();
    // The spinner sits beside a visible label, so it stays out of the a11y tree.
    await expect(canvas.queryByRole("progressbar")).toBeNull();
  },
};

export const AbortMenu: Story = {
  render: renderWith("installing"),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const toggle = canvas.getByRole("button", { name: /abort install/i });
    await userEvent.click(toggle);
    await expect(toggle).toHaveAttribute("aria-expanded", "true");
    // RMenu teleports its panel to <body>, outside the story canvas.
    const menu = await within(canvasElement.ownerDocument.body).findByRole(
      "menu",
    );
    await expect(
      within(menu).getByRole("button", { name: /abort install/i }),
    ).toBeEnabled();
  },
};

export const WaitingForInstaller: Story = {
  render: renderWith("awaiting_installer"),
};
