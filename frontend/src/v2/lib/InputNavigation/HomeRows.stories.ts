import type { Meta, StoryObj } from "@storybook/vue3-vite";
import { RBtn } from "@v2/lib";
import { expect, userEvent } from "storybook/test";
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import CardRow from "@/v2/components/shared/CardRow.vue";
import { useGridNav } from "@/v2/composables/useGridNav";
import { useSpatialNav } from "@/v2/composables/useSpatialNav";
import { pickSpatialTarget } from "@/v2/utils/spatialNav";
import {
  byLabel,
  labels,
  PlaygroundCallout,
  useFocusReadout,
} from "./playground.fixtures";

// The quirk: preferredCol only updates on Left/Right. Focus arriving via click, Tab, or
// spatial-nav leaves preferredCol at its last Left/Right value (0 on fresh mount).
// Three consequences documented here and exposed in play() tests -- do not fix useGridNav.

type Args = { bottomCount: number };

function homeRows({ withGridNav }: { withGridNav: boolean }) {
  return (args: Args) => ({
    components: { CardRow, RBtn, PlaygroundCallout },
    setup() {
      const root = ref<HTMLElement | null>(null);
      if (withGridNav) useGridNav(root); // mirrors Home.vue:149 exactly
      useSpatialNav().install();
      const focused = useFocusReadout();
      const nearestBelow = ref("n/a");

      function onFocusIn() {
        const active = document.activeElement as HTMLElement | null;
        const tracks =
          root.value?.querySelectorAll<HTMLElement>(".card-row__track");
        if (
          !active ||
          !tracks ||
          tracks.length < 2 ||
          !tracks[0].contains(active)
        )
          return;
        const from = active.getBoundingClientRect();
        // happy-dom returns zero rects; skip the readout there
        if (from.width === 0) {
          nearestBelow.value = "n/a";
          return;
        }
        const candidates = Array.from(
          tracks[1].children as HTMLCollectionOf<HTMLElement>,
        ).map((el) => ({ item: el, box: el.getBoundingClientRect() }));
        nearestBelow.value =
          pickSpatialTarget(from, candidates, "down")?.dataset.label ?? "n/a";
      }

      onMounted(() => document.addEventListener("focusin", onFocusIn));
      onBeforeUnmount(() => document.removeEventListener("focusin", onFocusIn));

      return {
        root,
        args,
        focused,
        nearestBelow,
        top: labels("Top", 30),
        bottom: computed(() => labels("Bottom", args.bottomCount)),
      };
    },
    template: `
      <div style="display: grid; gap: var(--r-space-4)">
        <PlaygroundCallout title="Try:" :keys="['→ x30','↓']">
          Scrub the top row all the way right, then press Down. Which card wins?
        </PlaygroundCallout>
        <div ref="root">
          <CardRow title="Continue playing">
            <RBtn
              v-for="l in top" :key="l"
              :data-label="l"
              variant="translucent"
              style="flex: 0 0 140px; height: 90px"
            >{{ l }}</RBtn>
          </CardRow>
          <CardRow title="Recently added">
            <RBtn
              v-for="l in bottom" :key="l"
              :data-label="l"
              variant="translucent"
              style="flex: 0 0 140px; height: 90px"
            >{{ l }}</RBtn>
          </CardRow>
        </div>
        <dl style="display: grid; grid-template-columns: max-content 1fr; gap: var(--r-space-1) var(--r-space-4); margin: 0; color: var(--r-color-fg-secondary)">
          <dt>RomM moves to</dt><dd data-testid="focused" style="margin: 0">{{ focused }}</dd>
          <dt>Visually below you</dt><dd data-testid="nearest-below" style="margin: 0">{{ nearestBelow }}</dd>
        </dl>
      </div>`,
  });
}

const meta: Meta<Args> = {
  title: "Input Navigation/Home rows",
  parameters: {
    layout: "fullscreen",
    docs: {
      description: {
        component: `
The \`preferredCol\` variable ([useGridNav index.ts L70](frontend/src/v2/composables/useGridNav/index.ts#L70)) only updates on ArrowLeft/Right presses, not on focus arriving via click, Tab, or spatial-nav.

Three consequences:

1. **Scrub to "Top 30", press Down:** focus goes to "Bottom 30" (same index), not the card visually below.
2. **Focus "Top 30" without Left/Right (click/Tab/spatial), press Down:** focus goes to "Bottom 1" because \`preferredCol\` is still 0.
3. **Bottom row shorter:** Down clamps to its last item. Up returns to "Top 30" because \`preferredCol\` is kept.

Compare with the \`SpatialOnlyComparison\` variant -- same rows with only \`useSpatialNav\` -- where Down always lands on the card visually below you.
        `.trim(),
      },
    },
  },
  args: { bottomCount: 30 },
  argTypes: {
    bottomCount: { control: { type: "number", min: 1, max: 30 } },
  },
  render: homeRows({ withGridNav: true }),
};

export default meta;
type Story = StoryObj<Args>;

export const Interactive: Story = {};

export const SpatialOnlyComparison: Story = {
  render: homeRows({ withGridNav: false }),
  parameters: {
    docs: {
      description: {
        story:
          "Same rows with only useSpatialNav: Down lands on the card visually below you.",
      },
    },
  },
};

// Pins today's behavior: scrub to Top 30, Down -> Bottom 30 (same index, not visual neighbor).
export const DownAfterScrubbing: Story = {
  globals: { input: "key" },
  play: async ({ canvasElement }) => {
    byLabel(canvasElement, "Top 29").focus();
    await userEvent.keyboard("{ArrowRight}");
    await expect(byLabel(canvasElement, "Top 30")).toHaveFocus();
    await userEvent.keyboard("{ArrowDown}");
    await expect(byLabel(canvasElement, "Bottom 30")).toHaveFocus();
  },
};

// Pins today's behavior: preferredCol ignores focus that arrives without Left/Right.
export const DownAfterFocusJump: Story = {
  globals: { input: "key" },
  play: async ({ canvasElement }) => {
    byLabel(canvasElement, "Top 30").focus();
    await userEvent.keyboard("{ArrowDown}");
    await expect(byLabel(canvasElement, "Bottom 1")).toHaveFocus();
  },
};

export const ShorterRowClampsAndReturns: Story = {
  args: { bottomCount: 6 },
  globals: { input: "key" },
  play: async ({ canvasElement }) => {
    byLabel(canvasElement, "Top 29").focus();
    await userEvent.keyboard("{ArrowRight}{ArrowDown}");
    await expect(byLabel(canvasElement, "Bottom 6")).toHaveFocus();
    await userEvent.keyboard("{ArrowUp}");
    await expect(byLabel(canvasElement, "Top 30")).toHaveFocus();
  },
};
