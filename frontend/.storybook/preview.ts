import "@mdi/font/css/materialdesignicons.css";
import { withThemeByClassName } from "@storybook/addon-themes";
import { setup, type Preview } from "@storybook/vue3-vite";
import { createPinia } from "pinia";
import { createMemoryHistory, createRouter } from "vue-router";
import { createVuetify } from "vuetify";
import "vuetify/styles";
import i18n from "../src/locales";
import storePermissions from "../src/stores/permissions";
import "../src/styles/common.css";
import "../src/styles/fonts.css";
import { dark, light } from "../src/styles/themes";
import { ChromeLabelsKey } from "../src/v2/lib/a11y/chromeLabels";
import "../src/v2/styles/global.css";
import { createChromeLabels } from "../src/v2/utils/chromeLabels";
import { GAMEPAD_GLOBAL_KEY } from "./gamepad/constants";
import { withGamepad } from "./gamepad/withGamepad";

/*
 * Gamepad POC (Storybook-only, draft):
 *
 * 1. globalTypes below register the manager toolbar toggle (Off / On).
 * 2. Decorator `withGamepad` wraps every story in GamepadStoryHost (see .storybook/gamepad/).
 * 3. When On, the host mounts GamepadInputLayer, which calls the same v2 composables as the app
 *    (useInputModality + useGamepad). Stories that need D-pad focus must opt in to grid nav
 *    (e.g. QA/Gamepad gallery uses useWrapGridNav + `.gamepad-cell` wrappers).
 * 4. Canvas status bar (connection, activity LEDs, last button) is preview-only UI; the toolbar
 *    caption stays "Gamepad: Off|On". manager.ts listens on the Storybook channel to sync labels
 *    and hide the default toolbar icon (see GAMEPAD_TOOLBAR_LABEL_EVENT in constants.ts).
 *
 * Per-story override: parameters.gamepad === true forces the layer on regardless of the toolbar.
 */

// Each story runs inside a Vue app with Pinia + i18n + Vuetify registered.
// v2 primitives are Vuetify-free at runtime — Vuetify stays registered only
// because some shared dependencies still pull it in. The visible theme for
// v2 stories comes from the `.r-v2-dark` / `.r-v2-light` class toggled on
// <html> by the theme switcher decorator below.
//
// permissionsStore is hydrated with admin grants so any primitive that
// consumes `useCan(...)` renders its enabled state. Stories that need to
// exercise role-based hiding can override per-story by calling
// `storePermissions().hydrateFromRole("viewer" | "editor" | null)`.
setup((app) => {
  app.use(createPinia());
  app.use(i18n);
  // Stories exercise the same injected-label path as the app, so a
  // primitive rendering an un-translated label fails here too.
  app.provide(ChromeLabelsKey, createChromeLabels());
  // A catch-all router so primitives that render real `<router-link>`s
  // (RBtn / RListItem / RMenuItem with `to`) resolve a proper `href`
  // instead of crashing on `router.resolve`. Any string path resolves.
  app.use(
    createRouter({
      history: createMemoryHistory(),
      routes: [{ path: "/:pathMatch(.*)*", component: { render: () => null } }],
    }),
  );
  app.use(
    createVuetify({
      theme: {
        defaultTheme: "dark",
        themes: { dark, light },
      },
    }),
  );

  // Seed an admin so stories render with every gated control available.
  storePermissions().hydrateFromResponse({
    is_admin: true,
    grants: [],
    hidden: { platforms: [], roms: [] },
  });
});

const preview: Preview = {
  globalTypes: {
    // Wired to withGamepad via GAMEPAD_GLOBAL_KEY; manager.ts keeps the button label in sync.
    [GAMEPAD_GLOBAL_KEY]: {
      description:
        "RomM gamepad layer (useGamepad + modality). Canvas status appears only while On.",
      toolbar: {
        title: "Gamepad",
        items: [
          { value: false, title: "🎮 Gamepad: Off" },
          { value: true, title: "🎮 Gamepad: On" },
        ],
        showName: true,
        dynamicTitle: false,
      },
    },
  },
  initialGlobals: {
    [GAMEPAD_GLOBAL_KEY]: false,
  },
  parameters: {
    layout: "centered",
    backgrounds: { disable: true },
    // Accessibility gate
    a11y: {
      test: "error",
    },
    controls: {
      matchers: {
        color: /(background|color)$/i,
        date: /Date$/i,
      },
    },
    // Sidebar order: build up from atoms to compound surfaces. Primitives
    // are the foundation everything else composes from, then form
    // controls, structural layout pieces, data displays, and finally
    // positioned UI (menus + overlays). Media (domain-aware icons) is
    // last because it's the most specialised. Categories not listed
    // here fall through to Storybook's default alphabetical sort.
    options: {
      storySort: {
        order: [
          "QA",
          "Primitives",
          "Forms",
          "Structural",
          "Data",
          "Menus",
          "Overlays",
          "Media",
        ],
      },
    },
  },
  decorators: [
    withGamepad,
    withThemeByClassName({
      themes: {
        dark: "r-v2 r-v2-dark v-theme--dark",
        light: "r-v2 r-v2-light v-theme--light",
      },
      defaultTheme: "dark",
      parentSelector: "html",
    }),
  ],
};

export default preview;
