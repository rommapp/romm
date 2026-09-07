import tailwindcss from "@tailwindcss/vite";
import vue from "@vitejs/plugin-vue";
import browserslist from "browserslist";
import { URL, fileURLToPath } from "node:url";
import { defineConfig, loadEnv } from "vite";
import mkcert from "vite-plugin-mkcert";
import { VitePWA } from "vite-plugin-pwa";
import vuetify, { transformAssetUrls } from "vite-plugin-vuetify";

// Vuetify components to preoptimize for faster dev startup
const VUETIFY_COMPONENTS = [
  "vuetify/components/transitions",
  "vuetify/components/VAlert",
  "vuetify/components/VAppBar",
  "vuetify/components/VAutocomplete",
  "vuetify/components/VAvatar",
  "vuetify/components/VBottomNavigation",
  "vuetify/components/VBtn",
  "vuetify/components/VBtnGroup",
  "vuetify/components/VBtnToggle",
  "vuetify/components/VCard",
  "vuetify/components/VCarousel",
  "vuetify/components/VCheckbox",
  "vuetify/components/VChip",
  "vuetify/components/VDataTable",
  "vuetify/components/VDialog",
  "vuetify/components/VDivider",
  "vuetify/components/VEmptyState",
  "vuetify/components/VExpansionPanel",
  "vuetify/components/VFileInput",
  "vuetify/components/VForm",
  "vuetify/components/VGrid",
  "vuetify/components/VHover",
  "vuetify/components/VIcon",
  "vuetify/components/VImg",
  "vuetify/components/VItemGroup",
  "vuetify/components/VLabel",
  "vuetify/components/VList",
  "vuetify/components/VMenu",
  "vuetify/components/VNavigationDrawer",
  "vuetify/components/VProgressCircular",
  "vuetify/components/VProgressLinear",
  "vuetify/components/VRating",
  "vuetify/components/VSelect",
  "vuetify/components/VSheet",
  "vuetify/components/VSkeletonLoader",
  "vuetify/components/VSlider",
  "vuetify/components/VSnackbar",
  "vuetify/components/VSpeedDial",
  "vuetify/components/VSwitch",
  "vuetify/components/VTabs",
  "vuetify/components/VTextarea",
  "vuetify/components/VTextField",
  "vuetify/components/VToolbar",
  "vuetify/components/VTooltip",
  "vuetify/components/VWindow",
];

// Maps browserslist browser ids to the esbuild-style ids that Vite's
// `build.cssTarget` understands. Engines not listed here (and_chr, samsung,
// kaios, ...) share a rendering engine with one of these or track "latest",
// so skipping them does not change the emitted prefixes.
const BROWSERSLIST_TO_ESBUILD = {
  chrome: "chrome",
  edge: "edge",
  firefox: "firefox",
  ios_saf: "ios",
  opera: "opera",
  safari: "safari",
};

// Translate the shared `.browserslistrc` baseline into Vite's CSS target
// format. Vite 8 minifies CSS with Lightning CSS, which auto-prefixes and
// down-levels from the standard property based on browser targets, but on the
// minify path it only reads `build.cssTarget` (esbuild-style ids), never
// `css.lightningcss.targets`. Deriving it here keeps `.browserslistrc` the
// single source of truth. Without targets Lightning CSS drops the generated
// `-webkit-backdrop-filter`, breaking every glass/blur surface in Safari.
function cssTargetsFromBrowserslist() {
  const lowest = {};
  for (const entry of browserslist()) {
    const [id, range] = entry.split(" ");
    const name = BROWSERSLIST_TO_ESBUILD[id];
    if (!name) continue;
    const version = range.split("-")[0]; // "16.4-16.5" -> "16.4"
    const asNumber = Number.parseFloat(version);
    if (lowest[name] === undefined || asNumber < lowest[name].asNumber) {
      lowest[name] = { asNumber, version };
    }
  }
  return Object.entries(lowest).map(
    ([name, { version }]) => `${name}${version}`,
  );
}

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  // Load ENV variables from the parent directory and the current directory.
  const envPrefixes = ["VITE", "DEV"];
  const env = {
    ...loadEnv(mode, "../", envPrefixes),
    ...loadEnv(mode, "./", envPrefixes),
  };

  const backendPort = env.DEV_PORT ?? "5000";
  const httpsMode = env.DEV_HTTPS === "true";
  const pwaDevEnabled = env.DEV_PWA === "true";

  return {
    optimizeDeps: {
      include: VUETIFY_COMPONENTS,
    },
    build: {
      target: "esnext",
      // Browser targets for CSS (prefixing + down-leveling) come from the
      // shared `.browserslistrc`. Never hand-write a `-webkit-` twin next to a
      // standard property: Lightning CSS collapses the pair to whichever is
      // declared last, so let it generate the prefixes from these targets.
      cssTarget: cssTargetsFromBrowserslist(),
    },
    plugins: [
      tailwindcss(),
      vue({
        template: { transformAssetUrls },
      }),
      vuetify({
        autoImport: true,
      }),
      VitePWA({
        injectRegister: null,
        manifest: {
          icons: [
            {
              src: "favicon.ico",
              sizes: "256x256",
              type: "image/ico",
              purpose: "any maskable",
            },
          ],
        },
        devOptions: {
          enabled: pwaDevEnabled,
          type: "module",
        },
      }),
      httpsMode &&
        mkcert({
          savePath: "/app/.vite-plugin-mkcert",
          hosts: ["localhost", "127.0.0.1", "romm.dev"],
        }),
    ],
    define: {
      "process.env": {},
      __VUE_PROD_HYDRATION_MISMATCH_DETAILS__: true,
    },
    resolve: {
      alias: {
        "@": fileURLToPath(new URL("./src", import.meta.url)),
        "@v2": fileURLToPath(new URL("./src/v2", import.meta.url)),
      },
      extensions: [".js", ".json", ".jsx", ".mjs", ".ts", ".tsx", ".vue"],
    },
    server: {
      watch: {
        // Never crawl the served library resources: this path is a symlink
        // into the user's library (covers, screenshots) and can hold hundreds
        // of thousands of files, which OOMs the dev server's file watcher.
        ignored: ["**/assets/romm/resources/**", "**/assets/romm/resources"],
      },
      proxy: {
        "/api": {
          target: `http://127.0.0.1:${backendPort}`,
          changeOrigin: false,
          secure: false,
        },
        "^/(?:ws|netplay)": {
          target: `http://127.0.0.1:${backendPort}`,
          changeOrigin: false,
          ws: true,
        },
        "/openapi.json": {
          target: `http://127.0.0.1:${backendPort}`,
          changeOrigin: false,
          rewrite: (path) => path.replace(/^\/openapi.json/, "/openapi.json"),
        },
      },
      port: httpsMode ? 8443 : 3000,
      allowedHosts: ["localhost", "127.0.0.1", "romm.dev"],
      ...(httpsMode
        ? {
            https: {
              cert: "/app/.vite-plugin-mkcert/dev.pem",
              key: "/app/.vite-plugin-mkcert/dev-key.pem",
            },
          }
        : {}),
    },
  };
});
