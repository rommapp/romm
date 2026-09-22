/**
 * QA story for the Storybook gamepad POC (see frontend/.storybook/preview.ts).
 *
 * How this story connects to the rest of the stack:
 *
 * 1. Toolbar "Gamepad: On" sets global gamepadInput → withGamepad → GamepadStoryHost mounts
 *    GamepadInputLayer (useGamepad + useInputModality from the app).
 * 2. useGamepad moves focus between elements marked as grid cells and sends A → click on the
 *    focused control. Plain RBtn/RChip nodes are not enough; they need a `.gamepad-cell` wrapper
 *    and a nav root wired with useWrapGridNav (same pattern as v2 gallery surfaces).
 * 3. The floating status bar above the canvas (pad id, LEDs, "Last event") is separate preview
 *    UI; this story's "Last action" line is local state to confirm clicks fired.
 *
 * Manual check: turn Gamepad On, press a face button once if Chrome has not exposed the pad yet,
 * then D-pad / stick to move focus and A to activate.
 */
import type { Meta, StoryObj } from "@storybook/vue3-vite";
import { onMounted, ref } from "vue";
import { useWrapGridNav } from "@/v2/composables/useWrapGridNav";
import RBtn from "@/v2/lib/primitives/RBtn/RBtn.vue";
import RChip from "@/v2/lib/primitives/RChip/RChip.vue";

const GRID_LABELS = [
  "Super Mario World",
  "Chrono Trigger",
  "Final Fantasy VI",
  "EarthBound",
  "Metroid",
  "Zelda",
  "Mega Man X",
  "Castlevania",
  "Secret of Mana",
] as const;

const meta: Meta = {
  title: "QA/Gamepad gallery",
  parameters: {
    layout: "fullscreen",
    docs: {
      description: {
        component:
          "Uses the same `useWrapGridNav` + `useGamepad` stack as the v2 gallery. " +
          "Turn **Gamepad: On**, press any face button once if Chrome hid the pad, " +
          "then D-pad / stick moves focus and **A** activates the focused tile.",
      },
    },
  },
};

export default meta;

type Story = StoryObj;

export const RomGrid: Story = {
  name: "ROM grid + filter chips",
  render: () => ({
    components: { RBtn, RChip },
    setup() {
      // useWrapGridNav attaches to this element; only `.gamepad-cell` descendants participate.
      const navRoot = ref<HTMLElement | null>(null);
      const lastAction = ref("—");
      const tags = ref([
        { id: 1, label: "Platform · SNES" },
        { id: 2, label: "Genre · RPG" },
        { id: 3, label: "Played" },
      ]);

      useWrapGridNav(navRoot, { cellSelector: ".gamepad-cell" });

      function pick(title: string) {
        lastAction.value = `Opened ${title}`;
      }

      function removeTag(id: number) {
        tags.value = tags.value.filter((t) => t.id !== id);
        lastAction.value = `Removed tag ${id}`;
      }

      function resetTags() {
        tags.value = [
          { id: 1, label: "Platform · SNES" },
          { id: 2, label: "Genre · RPG" },
          { id: 3, label: "Played" },
        ];
        lastAction.value = "Reset tags";
      }

      onMounted(() => {
        lastAction.value =
          "Waiting for pad focus (turn Gamepad On, then press A or a D-pad direction)";
      });

      return {
        navRoot,
        GRID_LABELS,
        lastAction,
        tags,
        pick,
        removeTag,
        resetTags,
      };
    },
    template: `
      <div
        style="
          min-height: 100vh;
          padding: 48px 32px 32px;
          box-sizing: border-box;
          display: flex;
          flex-direction: column;
          gap: 20px;
          align-items: center;
        "
      >
        <p
          style="
            margin: 0;
            max-width: 36rem;
            font: 12px/1.45 var(--r-font-family, system-ui, sans-serif);
            color: var(--r-color-fg-muted);
            text-align: center;
          "
        >
          Toolbar: Gamepad On. This grid uses <code>useWrapGridNav</code> like
          Platforms / Collections. D-pad or stick moves the focus ring; A clicks
          the focused tile or chip close button.
        </p>

        <!-- navRoot: required ref for useWrapGridNav; chips + ROM tiles share one wrap grid -->
        <div ref="navRoot" style="width: min(100%, 520px); display: flex; flex-direction: column; gap: 16px; align-items: stretch;">
          <div
            style="
              display: flex;
              flex-wrap: wrap;
              gap: 8px;
              justify-content: center;
            "
          >
            <div
              v-for="t in tags"
              :key="t.id"
              class="gamepad-cell"
              :data-focus-key="'tag-' + t.id"
            >
              <RChip
                variant="translucent"
                color="primary"
                size="small"
                closable
                @click:close="removeTag(t.id)"
              >
                {{ t.label }}
              </RChip>
            </div>
            <div class="gamepad-cell" data-focus-key="reset-tags">
              <RBtn size="small" variant="outlined" color="primary" @click="resetTags">
                Reset tags
              </RBtn>
            </div>
          </div>

          <p
            style="
              margin: 0;
              font: 11px/1.3 ui-monospace, monospace;
              color: var(--r-color-fg-faint);
              text-align: center;
            "
          >
            Last action: {{ lastAction }}
          </p>

          <div
            role="grid"
            aria-label="Sample ROM library"
            style="
              display: grid;
              grid-template-columns: repeat(3, minmax(140px, 1fr));
              gap: 12px;
            "
          >
            <div
              v-for="title in GRID_LABELS"
              :key="title"
              class="gamepad-cell"
              :data-focus-key="title"
            >
              <RBtn
                variant="translucent"
                color="primary"
                block
                style="min-height: 72px; white-space: normal; text-align: center"
                @click="pick(title)"
              >
                {{ title }}
              </RBtn>
            </div>
          </div>
        </div>
      </div>
    `,
  }),
};
