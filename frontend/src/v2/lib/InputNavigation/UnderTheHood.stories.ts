import type { Meta, StoryObj } from "@storybook/vue3-vite";
import { RBtn } from "@v2/lib";
import { onBeforeUnmount, onMounted, ref } from "vue";
import {
  PAD_BUTTON,
  type GamepadButtonEventDetail,
} from "@/v2/composables/useGamepad";
import { useGridNav } from "@/v2/composables/useGridNav";
import { useSpatialNav } from "@/v2/composables/useSpatialNav";
import { PlaygroundCallout } from "./playground.fixtures";

const BUTTONS = Object.entries(PAD_BUTTON);

// Snippet for views that want to react to a specific button press:
//
//   import type { GamepadButtonEventDetail } from "@/v2/composables/useGamepad";
//   useEventListener(window, "gamepad:buttondown", (e: CustomEvent<GamepadButtonEventDetail>) => {
//     if (e.detail.name === "y") openContextMenu();
//   });
//   useEventListener(window, "gamepad:exitchord", () => exitFullscreen());

const meta: Meta = {
  title: "Input Navigation/Under the hood",
  parameters: {
    layout: "padded",
  },
  globals: { input: "live" },
  render: () => ({
    components: { RBtn, PlaygroundCallout },
    setup() {
      const log = ref<string[]>([]);
      const push = (line: string) =>
        (log.value = [line, ...log.value].slice(0, 12));

      function onButton(e: Event) {
        const detail = (e as CustomEvent<GamepadButtonEventDetail>).detail;
        push(
          `gamepad:buttondown  name=${detail.name ?? "?"}  index=${detail.index}`,
        );
      }
      function onKey(e: KeyboardEvent) {
        if (!e.key.startsWith("Arrow")) return;
        // Read after grids and useSpatialNav have had their turn
        setTimeout(() =>
          push(`keydown ${e.key}  claimed=${e.defaultPrevented}`),
        );
      }

      const grid = ref<HTMLElement | null>(null);
      useGridNav(grid, {
        getRows: () => (grid.value ? [grid.value] : []),
      });
      useSpatialNav().install();

      onMounted(() => {
        window.addEventListener("gamepad:buttondown", onButton);
        window.addEventListener("keydown", onKey);
      });
      onBeforeUnmount(() => {
        window.removeEventListener("gamepad:buttondown", onButton);
        window.removeEventListener("keydown", onKey);
      });

      return { log, grid, BUTTONS };
    },
    template: `
      <div style="display: grid; gap: var(--r-space-6); max-width: 720px">
        <PlaygroundCallout title="Under the hood" :keys="['←','→','🎮 any']">
          Arrow through the row below or press a controller button. Every event is logged here.
          Set the toolbar Input to Live (real devices) to see controller events.
        </PlaygroundCallout>

        <div ref="grid" style="display: flex; gap: var(--r-space-2)">
          <RBtn data-label="Alpha" variant="translucent">Alpha</RBtn>
          <RBtn data-label="Beta" variant="translucent">Beta</RBtn>
          <RBtn data-label="Gamma" variant="translucent">Gamma</RBtn>
          <RBtn data-label="Delta" variant="translucent">Delta</RBtn>
        </div>

        <pre
          data-testid="log"
          style="
            margin: 0;
            padding: var(--r-space-3);
            background: var(--r-color-surface);
            border: 1px solid var(--r-color-border);
            border-radius: var(--r-radius-md);
            font-size: 0.8rem;
            color: var(--r-color-fg-secondary);
            min-height: 160px;
          "
        >{{ log.join('\\n') || '(no events yet)' }}</pre>

        <details>
          <summary style="cursor: pointer; color: var(--r-color-fg-muted); margin-bottom: var(--r-space-3)">Standard mapping (button index reference)</summary>
          <table style="border-collapse: collapse; font-size: 0.85rem; color: var(--r-color-fg-secondary)">
            <caption style="text-align: left; padding-bottom: var(--r-space-2); color: var(--r-color-fg)">W3C standard gamepad mapping</caption>
            <thead>
              <tr>
                <th style="text-align: left; padding: var(--r-space-1) var(--r-space-3) var(--r-space-1) 0; border-bottom: 1px solid var(--r-color-border)">Name</th>
                <th style="text-align: right; padding: var(--r-space-1) 0; border-bottom: 1px solid var(--r-color-border)">Index</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="[name, index] in BUTTONS" :key="name">
                <td style="padding: var(--r-space-1) var(--r-space-3) var(--r-space-1) 0">{{ name }}</td>
                <td style="text-align: right; font-variant-numeric: tabular-nums">{{ index }}</td>
              </tr>
            </tbody>
          </table>
        </details>
      </div>`,
  }),
};

export default meta;
export const Default: StoryObj = {};
