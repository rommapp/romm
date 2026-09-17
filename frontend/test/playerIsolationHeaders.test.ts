import { readFileSync } from "node:fs";
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

// The `~<pattern> "<header>";` entries of the COOP/COEP maps. nginx delimits
// those patterns by whitespace, so they carry no escaping to undo.
const MAP_ENTRY = /^\s*~(\S+)\s+"(?:require-corp|same-origin)";/gm;

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

// The plugin restates the nginx map instead of reading it, so a URL isolated
// in production but not in dev would otherwise only surface as SharedArrayBuffer
// being unavailable behind the dev server.
describe("the nginx COOP/COEP map", () => {
  it("holds the patterns the plugin restates", () => {
    const template = readFileSync(TEMPLATE, "utf8");
    const sources = [
      ...new Set([...template.matchAll(MAP_ENTRY)].map((entry) => entry[1]!)),
    ].map((source) => new RegExp(source).source);

    expect(sources.length).toBeGreaterThan(0);
    expect(sources.sort()).toEqual(
      ISOLATED_PLAYER_URLS.map((pattern) => pattern.source).sort(),
    );
  });
});
