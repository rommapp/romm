import "@mdi/font/css/materialdesignicons.css";
import { withThemeByClassName } from "@storybook/addon-themes";
import { setup, type Preview } from "@storybook/vue3-vite";
import { createPinia } from "pinia";
import { createVuetify } from "vuetify";
import "vuetify/styles";
import i18n from "../src/locales";
import storePermissions from "../src/stores/permissions";
import "../src/styles/common.css";
import "../src/styles/fonts.css";
import { dark, light } from "../src/styles/themes";
import "../src/v2/styles/global.css";
import { v2Dark, v2Light } from "../src/v2/theme/vuetify";

// Each story runs inside a Vue app with Pinia + i18n + Vuetify registered.
// The theme switcher toolbar (below) drives Vuetify's theme name, and the
// `.r-v2-dark` / `.r-v2-light` class on <body> drives the CSS custom
// properties used by v2 R-components.
//
// permissionsStore is hydrated with admin grants so any primitive that
// consumes `useCan(...)` renders its enabled state. Stories that need to
// exercise role-based hiding can override per-story by calling
// `storePermissions().hydrateFromRole("viewer" | "editor" | null)`.
setup((app) => {
  app.use(createPinia());
  app.use(i18n);
  app.use(
    createVuetify({
      theme: {
        defaultTheme: "v2-dark",
        themes: {
          dark,
          light,
          "v2-dark": v2Dark,
          "v2-light": v2Light,
        },
      },
    }),
  );

  storePermissions().hydrateFromRole("admin");
});

const preview: Preview = {
  parameters: {
    layout: "centered",
    backgrounds: { disable: true },
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
