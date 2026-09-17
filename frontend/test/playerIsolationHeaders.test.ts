import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it, vi } from "vitest";
import {
  ISOLATED_PLAYER_URLS,
  isIsolatedPlayerUrl,
  playerIsolationHeaders,
} from "../scripts/playerIsolationHeaders";

type Middleware = (
  req: { url?: string },
  res: { setHeader: (name: string, value: string) => void },
  next: () => void,
) => void;

/** Drive the plugin's server hook and hand back the middleware it registered. */
function middleware(): Middleware {
  let registered: Middleware | undefined;
  const { configureServer } = playerIsolationHeaders() as unknown as {
    configureServer: (server: {
      middlewares: { use: (fn: Middleware) => void };
    }) => void;
  };
  configureServer({
    middlewares: {
      use: (fn) => {
        registered = fn;
      },
    },
  });
  if (!registered) throw new Error("no middleware registered");
  return registered;
}

function headersFor(url: string | undefined): Record<string, string> {
  const headers: Record<string, string> = {};
  const next = vi.fn();
  middleware()(
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

describe("isIsolatedPlayerUrl", () => {
  it.each([
    "/rom/1/ejs",
    "/rom/1/jsdos",
    // The v2 players carry their state in the query, and nginx matches the
    // request URI, so the query string has to be allowed for explicitly.
    "/rom/1/ejs?core=snes9x",
    "/console/rom/1/play",
  ])("isolates %s", (url) => {
    expect(isIsolatedPlayerUrl(url)).toBe(true);
  });

  it.each([
    "/rom/1",
    "/rom/1/pico8",
    "/rom/1/ruffle",
    "/rom/1/stream",
    "/platform/2",
    "/api/roms/1/content/game.zip",
    "/assets/emulatorjs/data/loader.js",
  ])("leaves %s alone", (url) => {
    expect(isIsolatedPlayerUrl(url)).toBe(false);
  });
});

describe("playerIsolationHeaders", () => {
  it("isolates a player document", () => {
    expect(headersFor("/rom/1/ejs")).toEqual(ISOLATED);
  });

  it("leaves every other document embeddable", () => {
    expect(headersFor("/rom/1")).toEqual({});
  });

  it("passes a request with no URL through", () => {
    expect(headersFor(undefined)).toEqual({});
  });
});

// The dev server and nginx have to isolate the same documents, and nothing
// generates one list from the other, so the drift is what is tested.
describe("the nginx map it mirrors", () => {
  // Vitest roots at frontend/, so the template sits one level above it.
  const template = readFileSync(
    resolve(process.cwd(), "../docker/nginx/templates/default.conf.template"),
    "utf8",
  );

  it("isolates exactly the same URLs", () => {
    const nginx = [
      ...template.matchAll(/^\s*~(\S+)\s+"(?:require-corp|same-origin)";/gm),
    ].map((entry) => entry[1]);
    // nginx patterns are unescaped, since the delimiter is whitespace there.
    const mirrored = ISOLATED_PLAYER_URLS.map((pattern) =>
      pattern.source.replaceAll("\\/", "/"),
    );

    expect(nginx.length).toBeGreaterThan(0);
    expect(new Set(nginx)).toEqual(new Set(mirrored));
  });
});
