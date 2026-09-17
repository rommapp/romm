/**
 * playerIsolationHeaders: the dev server's twin of the nginx COOP/COEP map.
 *
 * Threaded EmulatorJS cores need SharedArrayBuffer, which only a cross-origin
 * isolated document exposes. In production nginx attaches the headers to the
 * player URLs alone, because the rest of the app embeds third-party images that
 * COEP would block. Nothing sits in front of the dev server, so it answers the
 * same URLs the same way.
 */
import type { Plugin } from "vite";

// One entry per entry of the map in docker/nginx/templates/default.conf.template,
// matched the same way: against the full request URI rather than the path, since
// there try_files rewrites the path to /index.html before the headers run.
const ISOLATED_PLAYER_URLS = [
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
