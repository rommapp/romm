import type { Decorator, Preview } from "@storybook/vue3-vite";
import { computed, defineAsyncComponent, defineComponent, watch } from "vue";
import {
  useInputModality,
  type InputModality,
} from "../src/v2/composables/useInputModality";

export const INPUT_GLOBAL = "input";

// "live" tracks real devices like the app shell; every other value pins data-input.
type StoryInputMode = InputModality | "live";

export const INPUT_TOOLBAR = {
  description: "Input modality (data-input on <html>)",
  toolbar: {
    title: "Input",
    icon: "pointerhand",
    dynamicTitle: true,
    items: [
      { value: "mouse", title: "Mouse" },
      { value: "touch", title: "Touch" },
      { value: "key", title: "Keyboard" },
      { value: "pad", title: "Gamepad" },
      { value: "live", title: "Live (real devices)" },
    ],
  },
} satisfies NonNullable<Preview["globalTypes"]>[string];

const { modality, install, setModality } = useInputModality();
let pinned: InputModality | null = null;

// Once installed the modality listeners are app-lifetime, so a pinned mode undoes
// their writes. Not sync: setModality writes data-input after it sets the ref.
const stopRepin = watch(modality, (next) => {
  if (pinned && next !== pinned) setModality(pinned);
});
import.meta.hot?.dispose(stopRepin);

function applyMode(mode: StoryInputMode) {
  if (mode === "live") {
    pinned = null;
    install();
    return;
  }
  pinned = mode;
  setModality(mode);
  // setModality skips the DOM write when the ref already holds the value.
  document.documentElement.dataset.input = mode;
}

// Unmounting stops useGamepad's poll loop, so the pad only drives stories that asked for it.
// Lazy so vitest.setup.ts doesn't cache useGamepad ahead of its tests' vue-router mock.
const GamepadLayer = defineAsyncComponent(async () => {
  const { useGamepad } = await import("../src/v2/composables/useGamepad");
  return defineComponent({
    setup() {
      useGamepad().install();
      return () => null;
    },
  });
});

export const withInputModality: Decorator = (story, context) => ({
  components: { story, GamepadLayer },
  setup() {
    // The Vue renderer keeps the story mounted on a toolbar change and
    // updates the reactive globals in place.
    const mode = computed(
      () => (context.globals[INPUT_GLOBAL] ?? "mouse") as StoryInputMode,
    );
    watch(mode, applyMode, { immediate: true });
    const padActive = computed(
      () => mode.value === "live" || mode.value === "pad",
    );
    return { padActive };
  },
  template: '<GamepadLayer v-if="padActive" /><story />',
});
