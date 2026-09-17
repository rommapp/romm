/**
 * playerIsolationHeaders: the dev server's stand-in for nginx's COOP/COEP map.
 *
 * Threaded EmulatorJS cores and js-dos need SharedArrayBuffer, which only a
 * cross-origin isolated document exposes, and only the player URLs may be
 * isolated, since the rest of the app embeds third-party images that COEP
 * would block. The URLs come from the nginx template so there is one list.
 */
import { readFileSync } from "node:fs";
import type { Connect, Plugin } from "vite";

// The `~<pattern> "<header>";` entries of the COOP/COEP maps. nginx delimits
// those patterns by whitespace, so they carry no escaping to undo.
const MAP_ENTRY = /^\s*~(\S+)\s+"(?:require-corp|same-origin)";/gm;

/** The URL patterns the nginx template isolates, as JS regexes. */
export function isolatedPlayerUrls(templatePath: string): RegExp[] {
  const template = readFileSync(templatePath, "utf8");
  const sources = new Set(
    [...template.matchAll(MAP_ENTRY)].map((entry) => entry[1]!),
  );
  if (sources.size === 0) {
    throw new Error(`No COOP/COEP map entries in ${templatePath}`);
  }
  return [...sources].map((source) => new RegExp(source));
}

// nginx matches the request URI rather than the path, since try_files rewrites
// the path to /index.html before it reaches the headers.
function isIsolated(patterns: readonly RegExp[], url: string): boolean {
  return patterns.some((pattern) => pattern.test(url));
}

// `vite preview` serves the built app with no nginx in front of it either, so
// it answers the player URLs the same way the dev server does.
export function playerIsolationHeaders(templatePath: string): Plugin {
  const patterns = isolatedPlayerUrls(templatePath);

  const isolate: Connect.NextHandleFunction = (req, res, next) => {
    if (isIsolated(patterns, req.url ?? "")) {
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
