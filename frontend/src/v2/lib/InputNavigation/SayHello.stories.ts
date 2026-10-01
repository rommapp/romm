import type { Meta, StoryObj } from "@storybook/vue3-vite";
import { RIcon } from "@v2/lib";
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { isPadEvent, PAD_BUTTON } from "@/v2/composables/useGamepad";
import { useInputModality } from "@/v2/composables/useInputModality";
import { PlaygroundCallout } from "./playground.fixtures";

const MODALITY_UI = {
  mouse: { icon: "mdi-mouse", label: "Mouse" },
  touch: { icon: "mdi-gesture-tap", label: "Touch" },
  key: { icon: "mdi-keyboard", label: "Keyboard" },
  pad: { icon: "mdi-controller", label: "Controller" },
} as const;

const BUTTONS = Object.entries(PAD_BUTTON);

const meta: Meta = {
  title: "Input Navigation/Say hello",
  parameters: { layout: "padded" },
  globals: { input: "live" },
  render: () => ({
    components: { RIcon, PlaygroundCallout },
    setup() {
      const { modality } = useInputModality();
      const ui = computed(
        () => MODALITY_UI[modality.value as keyof typeof MODALITY_UI],
      );
      const lastKey = ref<string | null>(null);
      const lastFromPad = ref(false);
      const pad = ref<{
        id: string;
        mapping: string;
        pressed: boolean[];
        axes: number[];
      } | null>(null);
      let raf = 0;

      function onKey(e: KeyboardEvent) {
        lastKey.value = e.key;
        lastFromPad.value = isPadEvent(e);
      }

      // Story-local poll: reads raw state for the lens, separate from useGamepad's loop.
      function poll() {
        const first =
          typeof navigator.getGamepads === "function"
            ? (navigator.getGamepads().find((p) => p?.connected) ?? null)
            : null;
        pad.value = first
          ? {
              id: first.id,
              mapping: first.mapping,
              pressed: first.buttons.map((b) => b.pressed),
              axes: [...first.axes],
            }
          : null;
        raf = requestAnimationFrame(poll);
      }

      onMounted(() => {
        window.addEventListener("keydown", onKey);
        if (typeof navigator.getGamepads === "function")
          raf = requestAnimationFrame(poll);
      });
      onBeforeUnmount(() => {
        window.removeEventListener("keydown", onKey);
        cancelAnimationFrame(raf);
      });

      return { ui, lastKey, lastFromPad, pad, BUTTONS };
    },
    template: `
      <div style="display: grid; gap: var(--r-space-6); max-width: 720px">
        <PlaygroundCallout title="Say hello" :keys="['←','↑','→','↓','Tab','🎮 any button']">
          Press an arrow key, move your mouse, or connect a controller and press any button.
          This panel shows what RomM sees.
        </PlaygroundCallout>

        <section aria-live="polite" style="display: flex; align-items: center; gap: var(--r-space-4)">
          <RIcon :icon="ui.icon" size="48" />
          <div>
            <div style="color: var(--r-color-fg-muted)">RomM thinks you're using</div>
            <div data-testid="modality" style="font-size: 1.6rem; color: var(--r-color-fg)">{{ ui.label }}</div>
          </div>
        </section>

        <p data-testid="last-key" style="margin: 0; color: var(--r-color-fg-secondary)">
          <template v-if="lastKey">Last key: <strong>{{ lastKey }}</strong>
            {{ lastFromPad ? "from your controller's D-pad" : "from your keyboard" }}</template>
          <template v-else>No keys yet. Try an arrow.</template>
        </p>

        <section v-if="!pad" style="color: var(--r-color-fg-muted)">
          No controller yet. Plug one in or pair it, then press a button to wake it up.
          Browsers only reveal a controller after its first press.
        </section>
        <section v-else style="display: grid; gap: var(--r-space-3)">
          <strong style="color: var(--r-color-fg)">Hello, {{ pad.id }}!</strong>
          <span v-if="pad.mapping !== 'standard'" style="color: var(--r-color-fg-muted)">
            Non-standard mapping: buttons may be labelled differently.
          </span>
          <ul style="display: grid; grid-template-columns: repeat(auto-fill, minmax(90px, 1fr)); gap: var(--r-space-2); list-style: none; padding: 0; margin: 0">
            <li v-for="[name, index] in BUTTONS" :key="name"
                :style="{
                  padding: 'var(--r-space-2)',
                  borderRadius: 'var(--r-radius-md)',
                  textAlign: 'center',
                  border: '1px solid var(--r-color-border)',
                  background: pad.pressed[index] ? 'var(--r-color-brand-primary)' : 'var(--r-color-surface)',
                  color: pad.pressed[index] ? 'var(--r-color-overlay-fg)' : 'var(--r-color-fg-secondary)'
                }">
              {{ name }}
            </li>
          </ul>
          <div style="display: flex; gap: var(--r-space-4)">
            <div v-for="(axes, stick) in [[pad.axes[0], pad.axes[1]], [pad.axes[2], pad.axes[3]]]" :key="stick"
                 style="position: relative; width: 64px; height: 64px; border: 1px solid var(--r-color-border); border-radius: var(--r-radius-md); background: var(--r-color-surface-hover)">
              <div :style="{
                position: 'absolute',
                width: '10px', height: '10px',
                borderRadius: '50%',
                background: 'var(--r-color-brand-primary)',
                left: 'calc(50% + ' + (axes[0] * 27) + 'px - 5px)',
                top: 'calc(50% + ' + (axes[1] * 27) + 'px - 5px)',
              }"></div>
            </div>
          </div>
        </section>
      </div>`,
  }),
};

export default meta;
export const Default: StoryObj = {};
