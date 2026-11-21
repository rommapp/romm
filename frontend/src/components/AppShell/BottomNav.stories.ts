import type { Decorator, Meta, StoryObj } from "@storybook/vue3-vite";
import { expect, userEvent, waitFor, within } from "storybook/test";
import { onMounted, onUnmounted } from "vue";
import { useRouter } from "vue-router";
import BottomNav from "./BottomNav.vue";

// A colourful backdrop so the glass blur and saturation have something to show.
const backdrop: Decorator = () => ({
  template: `
    <div style="position: relative; height: 100vh; overflow: hidden; background: linear-gradient(160deg, var(--r-color-brand-primary-solid), var(--r-color-bg) 45%, var(--r-color-brand-accent) 80%);">
      <div style="position: absolute; inset: auto 16px 24px; height: 180px; display: flex; gap: 12px;">
        <div style="flex: 1; border-radius: 12px; background: var(--r-color-romm-gold);"></div>
        <div style="flex: 1; border-radius: 12px; background: var(--r-color-success);"></div>
        <div style="flex: 1; border-radius: 12px; background: var(--r-color-info);"></div>
      </div>
      <story />
    </div>`,
});

function atRoute(path: string): Decorator {
  return () => ({
    setup() {
      const router = useRouter();
      onMounted(() => router.push(path));
    },
    template: "<story />",
  });
}

const reducedMotion: Decorator = () => ({
  setup() {
    const html = document.documentElement;
    onMounted(() => html.classList.add("r-reduced-motion"));
    onUnmounted(() => html.classList.remove("r-reduced-motion"));
  },
  template: "<story />",
});

const meta: Meta<typeof BottomNav> = {
  title: "AppShell/BottomNav",
  component: BottomNav,
  decorators: [backdrop],
  parameters: { layout: "fullscreen" },
  globals: { viewport: { value: "rommPhoneXs" } },
};

export default meta;
type Story = StoryObj<typeof BottomNav>;

const tab = (canvasElement: HTMLElement, name: string) =>
  within(canvasElement).getByRole("link", { name });

export const Default: Story = {
  decorators: [atRoute("/")],
  play: async ({ canvasElement, step }) => {
    await step("Home is active", async () => {
      await waitFor(() =>
        expect(tab(canvasElement, "Home")).toHaveClass(
          "r-segmented-control__btn--active",
        ),
      );
    });

    await step("Tapping Collections moves the selection", async () => {
      await userEvent.click(tab(canvasElement, "Collections"));
      await waitFor(() =>
        expect(tab(canvasElement, "Collections")).toHaveClass(
          "r-segmented-control__btn--active",
        ),
      );
      await expect(tab(canvasElement, "Home")).not.toHaveClass(
        "r-segmented-control__btn--active",
      );
    });
  },
};

export const PlatformsActive: Story = {
  decorators: [atRoute("/platforms")],
};

export const Light: Story = {
  decorators: [atRoute("/")],
  globals: { theme: "light" },
};

export const SmallPhone: Story = {
  decorators: [atRoute("/search")],
  globals: { viewport: { value: "mobile1" } },
};

export const KeyboardFocus: Story = {
  decorators: [atRoute("/")],
  globals: { input: "key" },
  play: async ({ canvasElement }) => {
    tab(canvasElement, "Platforms").focus();
    await expect(tab(canvasElement, "Platforms")).toHaveFocus();
  },
};

export const ReducedMotion: Story = {
  decorators: [reducedMotion, atRoute("/")],
};
