// The dev server's stand-in for nginx's COOP/COEP map. Only the player URLs
// are isolated: COEP would block the third-party images the rest of the app
// embeds.
import type { Connect, Plugin } from "vite";

// A copy of the `$coep_header`/`$coop_header` maps in
// docker/nginx/templates/default.conf.template; the test fails when they drift.
export const ISOLATED_PLAYER_URLS: readonly RegExp[] = [
  /^\/rom\/.*\/(ejs|jsdos)(\?|$)/,
  /^\/console\/rom\/[0-9]+\/play/,
];

// nginx matches the request URI rather than the path, since try_files rewrites
// the path to /index.html before it reaches the headers.
function isIsolated(url: string): boolean {
  return ISOLATED_PLAYER_URLS.some((pattern) => pattern.test(url));
}

// `vite preview` serves the built app with no nginx in front of it either, so
// it answers the player URLs the same way the dev server does.
export function playerIsolationHeaders(): Plugin {
  const isolate: Connect.NextHandleFunction = (req, res, next) => {
    if (isIsolated(req.url ?? "")) {
      res.setHeader("Cross-Origin-Embedder-Policy", "require-corp");
      res.setHeader("Cross-Origin-Opener-Policy", "same-origin");
    }
    next();
  };

  return {
    name: "romm:player-isolation-headers",
    apply: "serve",
    configureServer(server) {
      server.middlewares.use(isolate);
    },
    configurePreviewServer(server) {
      server.middlewares.use(isolate);
    },
  };
}
