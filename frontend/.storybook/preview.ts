import "@mdi/font/css/materialdesignicons.css";
import { withThemeByClassName } from "@storybook/addon-themes";
import { setup, type Preview } from "@storybook/vue3-vite";
import { createPinia } from "pinia";
import { createMemoryHistory, createRouter } from "vue-router";
import { createVuetify } from "vuetify";
import "vuetify/styles";
import i18n from "../src/locales";
import type { User } from "../src/stores/users";
import "../src/styles/common.css";
import "../src/styles/fonts.css";
import { dark, light } from "../src/styles/themes";
import { ChromeLabelsKey } from "../src/v2/lib/a11y/chromeLabels";
import "../src/v2/styles/global.css";
import { createChromeLabels } from "../src/v2/utils/chromeLabels";

// Pinia, i18n, and Vuetify are registered. v2 stories theme via `.r-v2-dark` /
// `.r-v2-light` on body; Vuetify stays for leftover shared deps.
setup(async (app) => {
  app.use(createPinia());
  app.use(i18n);
  // Stories exercise the same injected-label path as the app, so a
  // primitive rendering an un-translated label fails here too.
  app.provide(ChromeLabelsKey, createChromeLabels());
  // Catch-all memory router so `<router-link>` can resolve `href`.
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

  // vitest.setup imports this file. Loading auth here would construct axios
  // before any test's `vi.mock("@/services/api")`.
  if (import.meta.env.VITEST) return;

  const [{ default: storeAuth }, { default: storePermissions }] =
    await Promise.all([
      import("../src/stores/auth"),
      import("../src/stores/permissions"),
    ]);
  storePermissions().hydrateFromResponse({
    is_admin: true,
    grants: [],
    hidden: { platforms: [], roms: [] },
  });
  storeAuth().setCurrentUser({
    id: 1,
    username: "storybook",
    email: "storybook@localhost",
    enabled: true,
    role: "admin",
    oauth_scopes: [],
    avatar_path: "",
    last_login: null,
    last_active: null,
    created_at: "2026-01-01T00:00:00.000Z",
    updated_at: "2026-01-01T00:00:00.000Z",
  } satisfies User);
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
    // Sidebar: primitives first, then forms, layout, data, overlays, media.
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
