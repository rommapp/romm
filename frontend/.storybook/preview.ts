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
import "../src/v2/styles/global.css";

// Each story runs inside a Vue app with Pinia + i18n + Vuetify registered.
// v2 primitives are Vuetify-free at runtime — Vuetify stays registered only
// because some shared dependencies still pull it in. The visible theme for
// v2 stories comes from the `.r-v2-dark` / `.r-v2-light` class toggled on
// <body> by the theme switcher decorator below.
//
// permissionsStore is hydrated with admin grants so any primitive that
// consumes `useCan(...)` renders its enabled state. Stories that need to
// exercise role-based hiding can override per-story by calling
// `storePermissions().hydrateFromRole("viewer" | "editor" | null)`.
setup((app) => {
  app.use(createPinia());
  app.use(i18n);
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
    withThemeByClassName({
      themes: {
        dark: "r-v2 r-v2-dark",
        light: "r-v2 r-v2-light",
      },
      defaultTheme: "dark",
    }),
  ],
};

export default preview;
