import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it, vi } from "vitest";
import {
  ISOLATED_PLAYER_URLS,
  playerIsolationHeaders,
} from "../scripts/playerIsolationHeaders";

// Vitest roots at frontend/, so the template sits one level above it.
const TEMPLATE = resolve(
  process.cwd(),
  "../docker/nginx/templates/default.conf.template",
);

// The dev container mounts frontend/ alone, so the template is out of reach
// there; CI always has the whole repo, where the drift has to be caught.
const TEMPLATE_REACHABLE = existsSync(TEMPLATE) || Boolean(process.env.CI);

// The `~<pattern> "<header>";` entries of one map. nginx delimits those
// patterns by whitespace, so they carry no escaping to undo.
const MAP_ENTRY = /^\s*~(\S+)\s+"(?:require-corp|same-origin)";/gm;

/** The patterns of the `$request_uri` map feeding `variable`, as regex sources. */
function mapPatterns(variable: string): string[] {
  const template = readFileSync(TEMPLATE, "utf8");
  const block = new RegExp(
    `map \\$request_uri \\$${variable}\\s*\\{([^}]*)\\}`,
  ).exec(template);
  if (!block) throw new Error(`No $${variable} map in ${TEMPLATE}`);
  return [...block[1]!.matchAll(MAP_ENTRY)].map(
    (entry) => new RegExp(entry[1]!).source,
  );
}

type Middleware = (
  req: { url?: string },
  res: { setHeader: (name: string, value: string) => void },
  next: () => void,
) => void;

type ServerHook = "configureServer" | "configurePreviewServer";

/** Drive one of the plugin's server hooks and hand back its middleware. */
function middleware(hook: ServerHook = "configureServer"): Middleware {
  let registered: Middleware | undefined;
  const plugin = playerIsolationHeaders() as unknown as Record<
    ServerHook,
    (server: { middlewares: { use: (fn: Middleware) => void } }) => void
  >;
  plugin[hook]({
    middlewares: {
      use: (fn) => {
        registered = fn;
      },
    },
  });
  if (!registered) throw new Error("no middleware registered");
  return registered;
}

function headersFor(
  url: string | undefined,
  hook?: ServerHook,
): Record<string, string> {
  const headers: Record<string, string> = {};
  const next = vi.fn();
  middleware(hook)(
    { url },
    {
      setHeader: (name, value) => {
        headers[name] = value;
      },
    },
    next,
  );
  expect(next).toHaveBeenCalledOnce();
  return headers;
}

const ISOLATED = {
  "Cross-Origin-Embedder-Policy": "require-corp",
  "Cross-Origin-Opener-Policy": "same-origin",
};

describe("playerIsolationHeaders", () => {
  it.each([
    "/rom/1/ejs",
    "/rom/1/jsdos",
    // The v2 players carry their state in the query, and nginx matches the
    // request URI, so the query string has to be allowed for explicitly.
    "/rom/1/ejs?core=snes9x",
    "/console/rom/1/play",
  ])("isolates %s", (url) => {
    expect(headersFor(url)).toEqual(ISOLATED);
  });

  it.each([
    "/rom/1",
    "/rom/1/pico8",
    "/rom/1/ruffle",
    "/rom/1/stream",
    "/platform/2",
    "/api/roms/1/content/game.zip",
    "/assets/emulatorjs/data/loader.js",
  ])("leaves %s embeddable", (url) => {
    expect(headersFor(url)).toEqual({});
  });

  it("passes a request with no URL through", () => {
    expect(headersFor(undefined)).toEqual({});
  });

  // `vite preview` has no nginx in front of it either.
  it("isolates a player document on the preview server too", () => {
    expect(headersFor("/rom/1/ejs", "configurePreviewServer")).toEqual(
      ISOLATED,
    );
  });
});

// The plugin restates the nginx maps instead of reading them, and each map is
// checked on its own: a URL isolated by one header alone leaves
// SharedArrayBuffer unavailable just as an unlisted one does.
describe.skipIf(!TEMPLATE_REACHABLE)("the nginx COOP/COEP maps", () => {
  it.each(["coep_header", "coop_header"])(
    "the %s map holds the patterns the plugin restates",
    (variable) => {
      expect(mapPatterns(variable).sort()).toEqual(
        ISOLATED_PLAYER_URLS.map((pattern) => pattern.source).sort(),
      );
    },
  );
});
