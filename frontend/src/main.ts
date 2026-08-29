import { createApp } from "vue";
import App from "@/RomM.vue";
import "@/console/index.css";
import { localesReady } from "@/locales";
import { registerPlugins } from "@/plugins";
import router from "@/plugins/router";
import storeAuth from "@/stores/auth";
import storeConfig from "@/stores/config";
import storeHeartbeat from "@/stores/heartbeat";
import "@/styles/common.css";
import "@/styles/fonts.css";
import "@/styles/scrollbar.css";
import "@/v2/styles/global.css";

// Recover from stale chunks after a redeploy: hashed asset names change, so
// a tab opened before the deploy 404s (or gets HTML) on its next lazy import
// and the page goes blank. One reload picks up the new asset manifest; the
// timestamp guard avoids a reload loop when an asset is genuinely missing.
const CHUNK_RELOAD_KEY = "romm-chunk-reload-at";

function reloadOnceForStaleChunk(url?: string): boolean {
  const lastReload = Number(sessionStorage.getItem(CHUNK_RELOAD_KEY) ?? 0);
  if (Date.now() - lastReload < 60_000) return false;
  sessionStorage.setItem(CHUNK_RELOAD_KEY, String(Date.now()));
  if (url) {
    window.location.assign(url);
  } else {
    window.location.reload();
  }
  return true;
}

function isChunkLoadError(error: unknown): boolean {
  return (
    error instanceof Error &&
    /error loading dynamically imported module|failed to fetch dynamically imported module|importing a module script failed|unable to preload css/i.test(
      error.message,
    )
  );
}

window.addEventListener("vite:preloadError", (event) => {
  if (reloadOnceForStaleChunk()) event.preventDefault();
});

async function initializeData() {
  const heartbeatStore = storeHeartbeat();
  const authStore = storeAuth();
  const configStore = storeConfig();

  // Load initial data (config + heartbeat + user)
  await Promise.all([
    heartbeatStore.fetchHeartbeat(),
    authStore.fetchCurrentUser(),
    configStore.fetchConfig(),
  ]);
}

async function initializeApp() {
  const app = createApp(App);

  // Registrar vuetify + pinia + i18n + emitter
  registerPlugins(app);

  // Locale messages gate the router alongside the initial data: the guard
  // resolves the route title as soon as the router is installed, and with
  // messages still in flight it would set the raw key as the tab title.
  await Promise.all([initializeData(), localesReady]);

  // Route-level lazy imports fail outside vite's preload helper, so stale
  // chunks during navigation surface here instead of as vite:preloadError.
  router.onError((error, to) => {
    if (isChunkLoadError(error)) {
      reloadOnceForStaleChunk(to?.fullPath);
    }
  });

  app.use(router);

  app.mount("#app");
}

initializeApp();
