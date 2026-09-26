import type { Meta, StoryObj } from "@storybook/vue3-vite";
import { expect, userEvent, within } from "storybook/test";
import { ref } from "vue";
import { useWrapGridNav } from "@/v2/composables/useWrapGridNav";
import RBtn from "@/v2/lib/primitives/RBtn/RBtn.vue";

// Pick an input in the toolbar: "Keyboard" / "Gamepad" show the focus rings;
// "Gamepad" and "Live" drive the grid from a connected controller (D-pad moves, A clicks).

const TITLES = [
  "Super Metroid",
  "Chrono Trigger",
  "Final Fantasy VI",
  "EarthBound",
  "Mega Man X",
  "Castlevania",
  "Secret of Mana",
  "F-Zero",
  "Star Fox",
];

const meta: Meta = {
  title: "Input Navigation",
  parameters: { layout: "padded" },
  render: () => ({
    components: { RBtn },
    setup() {
      const gridRoot = ref<HTMLElement | null>(null);
      const lastPicked = ref<string | null>(null);
      useWrapGridNav(gridRoot, { cellSelector: ".input-nav-cell" });
      return { gridRoot, lastPicked, TITLES };
    },
    template: `
      <div style="display: grid; gap: 16px; max-width: 560px">
        <div
          ref="gridRoot"
          style="display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 12px"
        >
          <RBtn
            v-for="title in TITLES"
            :key="title"
            class="input-nav-cell"
            variant="translucent"
            @click="lastPicked = title"
          >
            {{ title }}
          </RBtn>
        </div>
        <p data-testid="last-picked" style="margin: 0; color: var(--r-color-fg-muted)">
          Picked: {{ lastPicked ?? "nothing yet" }}
        </p>
      </div>
    `,
  }),
};

export default meta;

type Story = StoryObj;

export const WrapGrid: Story = {};

export const KeyboardNavigation: Story = {
  globals: { input: "key" },
  play: async ({ canvasElement }) => {
    await expect(document.documentElement.dataset.input).toBe("key");
    const canvas = within(canvasElement);
    const first = canvas.getByRole("button", { name: TITLES[0] });
    first.focus();
    await userEvent.keyboard("{ArrowRight}");
    await expect(canvas.getByRole("button", { name: TITLES[1] })).toHaveFocus();
    await userEvent.keyboard("{Enter}");
    await expect(canvas.getByTestId("last-picked")).toHaveTextContent(
      TITLES[1],
    );
  },
};
