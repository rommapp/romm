import "@mdi/font/css/materialdesignicons.css";
import { withThemeByClassName } from "@storybook/addon-themes";
import { setup, type Preview } from "@storybook/vue3-vite";
import mitt from "mitt";
import { createPinia } from "pinia";
import { createMemoryHistory, createRouter } from "vue-router";
import { installBreakpointAttribute } from "../src/composables/useBreakpoint";
import { ChromeLabelsKey } from "../src/lib/a11y/chromeLabels";
import i18n from "../src/locales";
import storePermissions from "../src/stores/permissions";
import "../src/styles/fonts.css";
import "../src/styles/global.css";
import "../src/styles/reset.css";
import type { Events } from "../src/types/emitter";
import { createChromeLabels } from "../src/utils/chromeLabels";
import "./preview.css";
import { ROMM_STORYBOOK_VIEWPORTS } from "./rommViewports";
import {
  INPUT_DEFAULT,
  INPUT_GLOBAL,
  INPUT_TOOLBAR,
  withInputModality,
} from "./withInputModality";

// Mirror AppLayout/AuthLayout so html[data-bp] CSS matches useBreakpoint() in the iframe.
installBreakpointAttribute();

// Each story runs in a Vue app with Pinia + i18n. The `.r-dark` / `.r-light`
// class on <html> (set by the decorator below) picks the theme.
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
  // Snackbar and confirm composables inject the app-wide event bus.
  app.provide("emitter", mitt<Events>());
  // A catch-all router so primitives that render real `<router-link>`s
  // (RBtn / RListItem / RMenuItem with `to`) resolve a proper `href`
  // instead of crashing on `router.resolve`. Any string path resolves.
  app.use(
    createRouter({
      history: createMemoryHistory(),
      routes: [{ path: "/:pathMatch(.*)*", component: { render: () => null } }],
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
  tags: ["autodocs"],
  globalTypes: {
    [INPUT_GLOBAL]: INPUT_TOOLBAR,
  },
  initialGlobals: {
    viewport: { value: "rommDesktopMd" },
    [INPUT_GLOBAL]: INPUT_DEFAULT,
  },
  parameters: {
    layout: "centered",
    backgrounds: { disable: true },
    viewport: {
      options: ROMM_STORYBOOK_VIEWPORTS,
    },
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
    withInputModality,
    withThemeByClassName({
      themes: {
        dark: "r-app r-dark",
        light: "r-app r-light",
      },
      defaultTheme: "dark",
      parentSelector: "html",
    }),
  ],
};

export default preview;
