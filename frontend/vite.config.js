// Plugins
import vue from "@vitejs/plugin-vue";
import { VitePWA } from "vite-plugin-pwa";
import vuetify, { transformAssetUrls } from "vite-plugin-vuetify";
import mkcert from "vite-plugin-mkcert";

// Utilities
import { URL, fileURLToPath } from "node:url";
import { defineConfig, loadEnv } from "vite";

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  // Load ENV variables from the parent directory and the current directory.
  const envPrefixes = ["VITE", "DEV"];
  const env = {
    ...loadEnv(mode, "../", envPrefixes),
    ...loadEnv(mode, "./", envPrefixes),
  };
  const backendPort = env.DEV_PORT ?? "5000";

  return {
    build: {
      target: "esnext",
    },
    plugins: [
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
          enabled: true,
          type: "module",
        },
      }),
      env.DEV_HTTPS &&
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
      },
      extensions: [".js", ".json", ".jsx", ".mjs", ".ts", ".tsx", ".vue"],
    },
    server: {
      proxy: {
        "/api": {
          target: `http://127.0.0.1:${backendPort}`,
          changeOrigin: false,
          secure: false,
        },
        "/ws": {
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
      port: env.DEV_HTTPS ? 443 : 3000,
      allowedHosts: ["localhost", "127.0.0.1", "romm.dev"],
      ...(env.DEV_HTTPS
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
