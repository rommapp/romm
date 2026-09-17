import tailwindcss from "@tailwindcss/vite";
import vue from "@vitejs/plugin-vue";
import { URL, fileURLToPath } from "node:url";
import { defineConfig, loadEnv } from "vite";
import mkcert from "vite-plugin-mkcert";
import { VitePWA } from "vite-plugin-pwa";
import vuetify, { transformAssetUrls } from "vite-plugin-vuetify";
import { playerIsolationHeaders } from "./scripts/playerIsolationHeaders";
import { precompress } from "./scripts/precompress";

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
      // No `target` here: Vite's default baseline (chrome111, edge111,
      // firefox114, safari16.4, ios16.4) is what we want, and `cssTarget`
      // inherits it. Never set `esnext`, `cssTarget` inherits that too and
      // Lightning CSS then drops the generated `-webkit-backdrop-filter`,
      // breaking every glass surface in Safari. Never hand-write the
      // `-webkit-` twin either: Lightning CSS keeps only the last of the
      // pair, so the standard property is the one that gets dropped.
      //
      // AudioWorklet.addModule is only dependable with a real URL, and Vite
      // inlines any asset under 4KB as a data: URI, so keep the worklet out.
      assetsInlineLimit: (filePath) =>
        filePath.endsWith("pico8AudioWorklet.js") ? false : undefined,
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
      precompress(),
      playerIsolationHeaders(),
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
        ignored: [
          "**/assets/romm/resources/**",
          "**/assets/romm/resources",
          "**/assets/emulatorjs/**",
          "**/assets/ruffle/**",
          "**/assets/jsdos/**",
          "**/assets/pico8/**",
        ],
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
