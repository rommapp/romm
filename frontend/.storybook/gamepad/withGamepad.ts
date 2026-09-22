import type { Decorator } from "@storybook/vue3-vite";
import { GLOBALS_UPDATED } from "storybook/internal/core-events";
import { addons, useGlobals } from "storybook/preview-api";
import { onBeforeUnmount, onMounted, ref, watch } from "vue";
import GamepadStoryHost from "./GamepadStoryHost.vue";
import { GAMEPAD_GLOBAL_KEY } from "./constants";
import { isGamepadGlobalEnabled } from "./toolbarSync";

declare module "@storybook/vue3-vite" {
  interface Parameters {
    /** Force RomM gamepad translation for this story. */
    gamepad?: boolean;
  }
}

/**
 * Preview decorator: wraps each story in GamepadStoryHost.
 *
 * Reads `globals[GAMEPAD_GLOBAL_KEY]` from preview-api (and GLOBALS_UPDATED, because nested
 * Vue SFCs cannot call useGlobals). Passes `enabled` down to the host, which turns on
 * GamepadInputLayer + the canvas status bar. Does not touch story args or parameters except
 * `parameters.gamepad === true` (always enabled for that story).
 */
export const withGamepad: Decorator = (story, context) => {
  const [globals] = useGlobals();
  const forceGamepad = context.parameters.gamepad === true;

  return {
    components: { story, GamepadStoryHost },
    setup() {
      const enabled = ref(
        forceGamepad || isGamepadGlobalEnabled(globals.value),
      );

      const syncEnabled = (nextGlobals?: Record<string, unknown>) => {
        enabled.value =
          forceGamepad || isGamepadGlobalEnabled(nextGlobals ?? globals.value);
      };

      watch(
        () => globals.value?.[GAMEPAD_GLOBAL_KEY],
        () => syncEnabled(),
      );

      type GlobalsUpdatedPayload = { globals: Record<string, unknown> };
      const onGlobalsUpdated = (payload: GlobalsUpdatedPayload) => {
        syncEnabled(payload.globals);
      };

      onMounted(() => {
        syncEnabled();
        addons.getChannel().on(GLOBALS_UPDATED, onGlobalsUpdated);
      });

      onBeforeUnmount(() => {
        addons.getChannel().off(GLOBALS_UPDATED, onGlobalsUpdated);
      });

      return { enabled };
    },
    template:
      '<GamepadStoryHost :enabled="enabled"><story /></GamepadStoryHost>',
  };
};
