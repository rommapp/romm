/**
 * playerIsolationHeaders: the dev server's twin of the nginx COOP/COEP map.
 *
 * Threaded EmulatorJS cores need SharedArrayBuffer, which only a cross-origin
 * isolated document exposes, and only the player URLs may be isolated, since
 * the rest of the app embeds third-party images that COEP would block.
 */
import type { Plugin } from "vite";

// One entry per entry of the map in docker/nginx/templates/default.conf.template,
// matched against the request URI as it is there, since try_files rewrites the
// path to /index.html before nginx reaches the headers.
export const ISOLATED_PLAYER_URLS = [
  /^\/rom\/.*\/(ejs|jsdos)(\?|$)/,
  /^\/console\/rom\/[0-9]+\/play/,
];

/** Whether a request URI addresses a player document that must be isolated. */
export function isIsolatedPlayerUrl(url: string): boolean {
  return ISOLATED_PLAYER_URLS.some((pattern) => pattern.test(url));
}

export function playerIsolationHeaders(): Plugin {
  return {
    name: "romm:player-isolation-headers",
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        if (isIsolatedPlayerUrl(req.url ?? "")) {
          res.setHeader("Cross-Origin-Embedder-Policy", "require-corp");
          res.setHeader("Cross-Origin-Opener-Policy", "same-origin");
        }
        next();
      });
    },
  };
}
